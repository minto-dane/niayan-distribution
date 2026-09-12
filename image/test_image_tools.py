# SPDX-License-Identifier: BSD-3-Clause
"""Small packaging regressions; the boot and install tests use real VMs."""
import importlib.util
import hashlib
import io
import json
from pathlib import Path
import subprocess
import socket
import tempfile
import tarfile
import unittest
from unittest import mock
import time
from vm_console import Guest, retire_install_disks

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('collect_sources', HERE / 'collect-sources.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
spec = importlib.util.spec_from_file_location('prepare_image', HERE / 'prepare.py')
preparer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparer)
spec = importlib.util.spec_from_file_location('record_build', HERE / 'record-build.py')
recorder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recorder)
spec = importlib.util.spec_from_file_location('completion', HERE.parent / 'release/complete-sources.py')
completion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(completion)


class ImageComparison(unittest.TestCase):
    def test_equal_bytes_require_equal_inputs_and_changed_bytes_fail(self):
        with tempfile.TemporaryDirectory(prefix='nia-image-comparison-') as temporary:
            roots = [Path(temporary) / name for name in ('first', 'second')]
            for root in roots:
                (root / 'live').mkdir(parents=True)
                (root / 'input-manifest.json').write_text('{"fixture":1}\n')
                (root / 'live/fixture.iso').write_bytes(b'comparison fixture only')
            artifacts = [recorder.identity(roots[0] / 'live/fixture.iso', roots[0])]
            self.assertEqual(recorder.compare_images(*roots, artifacts)['result'], 'pass')
            (roots[1] / 'input-manifest.json').write_text('{"fixture":2}\n')
            self.assertEqual(recorder.compare_images(*roots, artifacts)['result'], 'fail')
            (roots[1] / 'input-manifest.json').write_text('{"fixture":1}\n')
            (roots[1] / 'live/fixture.iso').write_bytes(b'different actual bytes')
            self.assertEqual(recorder.compare_images(*roots, artifacts)['result'], 'fail')
            (roots[1] / 'live/fixture.iso').unlink()
            self.assertEqual(recorder.compare_images(*roots, artifacts)['result'], 'fail')


class SourceAssociation(unittest.TestCase):
    def test_signed_kernel_source_control_closes_missing_udeb_reference(self):
        with tempfile.TemporaryDirectory(prefix='nia-kernel-source-') as temporary:
            archive = Path(temporary) / 'signed.tar.xz'

            def write_control(data, symlink=False):
                with tarfile.open(archive, 'w:xz') as stream:
                    member = tarfile.TarInfo('source-template/debian/control')
                    member.size = len(data)
                    if symlink:
                        member.type = tarfile.SYMTYPE
                        member.linkname = '/etc/passwd'
                    stream.addfile(member, io.BytesIO(data))

            write_control(b'Package: linux-image-fixture\nBuilt-Using: linux (= 6.12.94-1)\n')
            self.assertEqual(completion.kernel_references(archive), [('linux', '6.12.94-1')])
            write_control(b'Package: kernel-image-fixture-di\n')
            with self.assertRaisesRegex(ValueError, 'lacks original'):
                completion.kernel_references(archive)
            write_control(b'Built-Using: linux (= ${source:Version})\n')
            with self.assertRaisesRegex(ValueError, 'unsupported'):
                completion.kernel_references(archive)
            write_control(b'', symlink=True)
            with self.assertRaisesRegex(ValueError, 'unexpected'):
                completion.kernel_references(archive)

    def test_historical_architectures_are_alternatives_and_errors_fail(self):
        with tempfile.TemporaryDirectory(prefix='nia-history-test-') as temporary:
            calls = []

            def download(command, **kwargs):
                architecture = command[command.index('--architecture') + 1]
                calls.append(architecture)
                if architecture == 'amd64':
                    return subprocess.CompletedProcess(command, 2,
                        'debsnap: No binary packages found for fixture version 1.0 on amd64\n')
                directory = Path(command[command.index('--destdir') + 1])
                directory.mkdir()
                (directory / 'fixture_1.0_all.udeb').write_bytes(b'fixture')
                return subprocess.CompletedProcess(command, 0, '')

            target = Path(temporary) / 'collected'
            with mock.patch.object(collector.subprocess, 'run', side_effect=download):
                collector.historical_download(target, 'fixture', '1.0', binary=True)
            self.assertEqual(calls, ['amd64', 'all'])
            self.assertEqual((target / 'fixture_1.0_all.udeb').read_bytes(), b'fixture')
            with mock.patch.object(collector.subprocess, 'run', return_value=
                    subprocess.CompletedProcess(['debsnap'], 2, 'TLS retrieval failed')) as run:
                with self.assertRaises(subprocess.CalledProcessError):
                    collector.historical_download(Path(temporary) / 'failed', 'fixture', '1.0', binary=True)
                self.assertEqual(run.call_count, 1)

    def test_live_inventory_requires_every_exact_binary_version(self):
        with tempfile.TemporaryDirectory(prefix='nia-live-inventory-') as temporary:
            root = Path(temporary)
            (root / 'live').mkdir()
            (root / 'live/fixture.packages').write_text('fixture:amd64\t2:1.0-1+b2\n')
            with self.assertRaisesRegex(ValueError, 'missing from source associations'):
                collector.verify_live_inventory(root, {('fixture', '2:1.0-1'): None})
            report = collector.verify_live_inventory(root, {('fixture', '2:1.0-1+b2'): None})
            self.assertEqual(report['packages'], 1)
            self.assertEqual(report['missing_binary_associations'], [])

    def test_installer_build_identity_preserves_source_version(self):
        for flavor in ('isolinux', 'gtk'):
            self.assertEqual(collector.installer_identity('cdrom-' + flavor + '-20250803+deb13u6'),
                             ('debian-installer', '20250803+deb13u6'))
        with self.assertRaises(ValueError):
            collector.installer_identity('unknown-format')

    def test_source_archives_are_checked_against_exact_control(self):
        with tempfile.TemporaryDirectory(prefix='nia-dsc-test-') as temporary:
            root = Path(temporary)
            archive = root / 'fixture.tar.xz'
            data = b'archive fixture, not executed'
            archive.write_bytes(data)
            (root / 'fixture.dsc').write_text(
                'Source: fixture-source\nVersion: 2:1.0-1\nChecksums-Sha256:\n '
                + hashlib.sha256(data).hexdigest() + ' ' + str(len(data)) + ' fixture.tar.xz\n')
            collector.verify_source_archives(root, 'fixture-source', '2:1.0-1')
            with self.assertRaisesRegex(ValueError, 'version mismatch'):
                collector.verify_source_archives(root, 'fixture-source', '2:1.0-2')
            archive.write_bytes(b'wrong bytes')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                collector.verify_source_archives(root, 'fixture-source', '2:1.0-1')

    def identity(self, version, source=None, extra='', references=False):
        with tempfile.TemporaryDirectory(prefix='nia-image-source-test-') as temporary:
            root = Path(temporary)
            (root / 'package/DEBIAN').mkdir(parents=True)
            control = ('Package: fixture-binary\nVersion: ' + version + '\n'
                       'Architecture: all\nMaintainer: Fixture <fixture@example.invalid>\n'
                       'Description: source association test only\n')
            if source is not None:
                control += 'Source: ' + source + '\n'
            control += extra
            (root / 'package/DEBIAN/control').write_text(control)
            package = root / 'fixture.deb'
            subprocess.run(['dpkg-deb', '--build', '--root-owner-group',
                            str(root / 'package'), str(package)],
                           check=True, capture_output=True)
            return (collector.source_references(package) if references
                    else collector.source_identity(package))

    def test_binary_nmu_uses_explicit_source_version_and_epoch(self):
        self.assertEqual(self.identity('2:1.0-2+b3', 'fixture-source (2:1.0-2)'),
                         ('fixture-source', '2:1.0-2'))

    def test_source_name_without_version_preserves_binary_version(self):
        self.assertEqual(self.identity('1.0-1', 'fixture-source'),
                         ('fixture-source', '1.0-1'))

    def test_missing_source_field_preserves_identity(self):
        self.assertEqual(self.identity('1.0~rc1+git123'),
                         ('fixture-binary', '1.0~rc1+git123'))

    def test_no_invented_bin_nmu_source_version(self):
        self.assertEqual(self.identity('1.0-1+b2'), ('fixture-binary', '1.0-1+b2'))

    def test_signed_wrapper_retains_actual_kernel_and_static_sources(self):
        self.assertEqual(self.identity('6.12.107+1', 'linux-signed-amd64',
                         'Built-Using: linux (= 6.12.107-1)\n'
                         'Static-Built-Using: fixture-static (= 2:1.2-3)\n', True),
                         [('fixture-static', '2:1.2-3'), ('linux', '6.12.107-1'),
                          ('linux-signed-amd64', '6.12.107+1')])

    def test_additional_source_requires_exact_version(self):
        with self.assertRaisesRegex(ValueError, 'non-exact'):
            self.identity('1.0', extra='Built-Using: fixture-other (>= 1.0)\n', references=True)


class PreparationBoundaries(unittest.TestCase):
    def test_committed_file_modes_do_not_depend_on_checkout_permissions(self):
        with tempfile.TemporaryDirectory(prefix='nia-image-archive-test-') as temporary:
            workspace = Path(temporary)
            source = workspace / 'assurance'
            (source / 'packaging/nia').mkdir(parents=True)
            (source / 'LICENSE').write_text('fixture license\n')
            (source / 'packaging/nia/artifact.json').write_text('{"executables": []}\n')
            (source / 'tracked').write_text('committed bytes\n')
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            subprocess.run(['git', 'add', '.'], cwd=source, check=True)
            subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                            '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture'], cwd=source, check=True)
            (source / 'tracked').chmod(0o600)
            target = workspace / 'staged'
            preparer.stage_component(workspace, target, 'assurance')
            self.assertEqual((target / 'tracked').read_text(), 'committed bytes\n')
            self.assertEqual((target / 'tracked').stat().st_mode & 0o777, 0o644)

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory(prefix='nia-image-output-test-') as temporary:
            output = Path(temporary)
            marker = output / 'preserve'
            marker.write_text('existing work')
            with self.assertRaises(FileExistsError):
                preparer.prepare(output, output, 'kde')
            self.assertEqual(marker.read_text(), 'existing work')
            self.assertEqual(list(output.iterdir()), [marker])

    def test_dirty_component_refused_before_copy(self):
        with tempfile.TemporaryDirectory(prefix='nia-image-git-test-') as temporary:
            workspace = Path(temporary)
            source = workspace / 'assurance'
            source.mkdir()
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            (source / 'local-change').write_text('not committed')
            target = workspace / 'output'
            with self.assertRaisesRegex(ValueError, 'commit component changes'):
                preparer.stage_component(workspace, target, 'assurance')
            self.assertFalse(target.exists())


class SerialAcceptance(unittest.TestCase):
    def test_failure_already_received_after_login_is_not_lost(self):
        with tempfile.TemporaryDirectory(prefix='nia-serial-test-') as temporary:
            receiver, sender = socket.socketpair()
            with receiver, sender:
                guest = Guest([], temporary, timeout=1)
                guest.channel = receiver
                guest.log = io.BytesIO()
                guest.start = time.monotonic()
                receiver.settimeout(0.01)
                try:
                    sender.sendall(b'login: user\r\r\nNIAOS_LIVE_PROBE_FAIL\r\r\n')
                    guest.expect(b'login:')
                    with self.assertRaisesRegex(RuntimeError, 'acceptance failed'):
                        guest.expect(b'NIAOS_LIVE_PROBE_PASS', b'NIAOS_LIVE_PROBE_FAIL')
                finally:
                    guest.close()


class DiskRetirement(unittest.TestCase):
    def fixture(self, root):
        paths = [root / name / 'installed.qcow2' for name in
                 ('install-uefi-offline', 'install-bios-network')]
        for path in paths:
            path.parent.mkdir()
            path.write_bytes(b'owned fixture disk')
        (root / 'report.json').write_text('{"preserve":true}')
        return paths

    def test_success_removes_only_disks_and_records_allocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.fixture(root)
            records = []
            retire_install_disks(root, records)
            self.assertTrue(all(not path.exists() for path in paths))
            self.assertEqual([row['state'] for row in records], ['removed', 'removed'])
            self.assertTrue(all(row['logical_bytes'] == len(b'owned fixture disk') for row in records))
            self.assertEqual(json.loads((root / 'report.json').read_text()), {'preserve': True})
            with self.assertRaises(ValueError):
                retire_install_disks(root, records)

    def test_second_symlink_refuses_before_first_deletion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self.fixture(root)
            second.unlink()
            second.symlink_to(first)
            with self.assertRaises(OSError):
                retire_install_disks(root, [])
            self.assertEqual(first.read_bytes(), b'owned fixture disk')
            self.assertTrue(second.is_symlink())

    def test_busy_disk_refuses_before_any_deletion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.fixture(root)
            code = ('import fcntl,sys; f=open(sys.argv[1],"r+b"); '
                    'fcntl.lockf(f,fcntl.LOCK_EX); print("locked",flush=True); sys.stdin.read()')
            with subprocess.Popen(['python3', '-I', '-c', code, str(paths[1])],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE) as child:
                try:
                    self.assertEqual(child.stdout.readline(), b'locked\n')
                    with self.assertRaises(BlockingIOError):
                        retire_install_disks(root, [])
                    self.assertTrue(all(path.is_file() for path in paths))
                finally:
                    child.communicate(timeout=3)

    def test_suite_retirement_follows_complete_matrix(self):
        spec = importlib.util.spec_from_file_location('image_suite', HERE / 'test-suite.py')
        suite = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(suite)
        for mode in ('normal', 'retain', 'failure'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                iso = root / 'fixture.iso'
                iso.write_bytes(b'fixture')
                output = root / 'acceptance'
                completed = []

                def run(command, **kwargs):
                    target = Path(command[command.index('--output') + 1])
                    target.mkdir()
                    if target.name.startswith('install-'):
                        (target / 'installed.qcow2').write_bytes(b'owned fixture disk')
                    if target.name == 'installed-secure-boot':
                        self.assertTrue((output/'install-uefi-offline/installed.qcow2').is_file())
                        self.assertTrue((output/'install-bios-network/installed.qcow2').is_file())
                        if mode == 'failure':
                            raise subprocess.CalledProcessError(1, command)
                    (target / 'report.json').write_text('{"result":"pass"}')
                    completed.append(target.name)

                argv = ['test-suite.py', '--iso', str(iso), '--output', str(output)]
                if mode == 'retain':
                    argv.append('--retain-disks')
                with mock.patch.object(suite.sys, 'argv', argv), \
                     mock.patch.object(suite, 'install_interrupt_handler'), \
                     mock.patch.object(suite.subprocess, 'run', side_effect=run):
                    if mode == 'failure':
                        with self.assertRaises(subprocess.CalledProcessError):
                            suite.main()
                    else:
                        suite.main()
                report = json.loads((output / 'report.json').read_text())
                self.assertEqual(report['result'], 'fail' if mode == 'failure' else 'pass')
                self.assertEqual(len(completed), 5 if mode == 'failure' else 6)
                self.assertEqual((output/'install-uefi-offline/installed.qcow2').exists(), mode != 'normal')
                self.assertTrue(iso.is_file())


if __name__ == '__main__':
    unittest.main()
