# SPDX-License-Identifier: MIT
"""Exercise real public artifact entry points with no available system writer."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from interim_commands import display
from interim_package import encode
from nia_common import canonical, sha
from package_cli import UsageError, parse
from test_interim_package import fixture


class InterimCommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifest, self.artifacts = fixture()
        self.control = self.root / 'control.json'
        self.control.write_bytes(canonical(self.manifest))
        for key, data in self.artifacts.items():
            (self.root / (key + '.deb')).write_bytes(data)
        self.bindir = Path(__file__).resolve().parent / 'bin'

    def command(self, name, *args):
        return subprocess.run([str(self.bindir / name), *map(str, args)], cwd=self.root,
                              env={'PATH': str(self.root), 'HOME': str(self.root), 'LC_ALL': 'C.UTF-8'},
                              capture_output=True, text=True, timeout=10)

    def build(self, work='work'):
        result = self.command('epkg', '-w', self.root / work, '-e', self.control, 'fix001')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        outputs = list((self.root / work / 'fix001').glob('*.epkg'))
        self.assertEqual(len(outputs), 1)
        self.assertEqual(result.stdout, 'Package file is: ' + str(outputs[0]) + '\n')
        return outputs[0]

    def test_real_build_display_and_reproducible_bytes(self):
        first, second = self.build('one'), self.build('two')
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertIn(sha(first.read_bytes()), first.name)
        result = self.command('emgr', '-d', '-e', first)
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        self.assertEqual(result.stdout, 'EFIX LABEL: fix001\nPACKAGE: sample-bin\n'
                         'LEVEL: 1:2.0-4\nFILE NUMBER: 1\nLOCATION: /sample\n')
        alias = self.command('emgr', '-dv1', first)
        self.assertEqual((alias.returncode, alias.stdout, alias.stderr),
                         (result.returncode, result.stdout, result.stderr))
        self.assertFalse((self.root / 'sample').exists())

    def test_detail_is_original_metadata_and_not_installed_state(self):
        output = self.build()
        result = self.command('emgr', '-dv3', '-e', output)
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        for text in ('BASE LEVEL: 1:2.0-3+b1\n', 'REBOOT REQUIRED: no\n',
                     'ACTIVATION: service-restart\n', 'FILE TYPE: regular\n',
                     'SIZE: 13\n', 'SHA256: ' + sha(b'fixed payload') + '\n',
                     'PUBLISHER AUTHENTICATION: not verified\n'):
            self.assertIn(text, result.stdout)
        self.assertNotIn('STABLE', result.stdout)

    def test_default_work_directory(self):
        result = self.command('epkg', '-e', self.control, 'fix001')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list((self.root / 'epkgwork/fix001').glob('*.epkg'))), 1)

    def test_output_never_overwritten_and_failure_uses_stderr(self):
        output = self.build()
        before = output.read_bytes()
        result = self.command('epkg', '-w', self.root / 'work', '-e', self.control, 'fix001')
        self.assertEqual((result.returncode, result.stdout), (1, ''))
        self.assertTrue(result.stderr.startswith('epkg: '))
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(len(list(output.parent.iterdir())), 1)

    def test_label_binding_and_corrupt_input_precede_output_creation(self):
        result = self.command('epkg', '-w', self.root / 'work', '-e', self.control, 'other')
        self.assertEqual((result.returncode, result.stdout), (1, ''))
        self.assertFalse((self.root / 'work').exists())
        key = next(iter(self.artifacts))
        (self.root / (key + '.deb')).write_bytes(b'corrupt')
        result = self.command('epkg', '-w', self.root / 'work', '-e', self.control, 'fix001')
        self.assertEqual((result.returncode, result.stdout), (1, ''))
        self.assertFalse((self.root / 'work').exists())

    def test_work_directory_symlink_is_not_followed(self):
        destination = self.root / 'destination'
        destination.mkdir()
        (self.root / 'work').symlink_to(destination)
        result = self.command('epkg', '-w', self.root / 'work', '-e', self.control, 'fix001')
        self.assertEqual((result.returncode, result.stdout), (1, ''))
        self.assertEqual(list(destination.iterdir()), [])

    def test_display_corrupt_or_symlink_package_emits_no_partial_report(self):
        raw = encode(self.manifest, self.artifacts)
        corrupt = self.root / 'bad.epkg'
        corrupt.write_bytes(raw[:-1])
        for path in (corrupt, self.root / 'link.epkg'):
            if not path.exists():
                path.symlink_to(corrupt)
            result = self.command('emgr', '-d', '-e', path)
            self.assertEqual((result.returncode, result.stdout), (1, ''))
            self.assertTrue(result.stderr.startswith('emgr: '))

    def test_malformed_control_reports_failure_without_traceback(self):
        for raw in (b'{"created_at":' + b'9' * 5000 + b'}',
                    b'[' * 2000 + b']' * 2000, b'{"label":"one","label":"two"}'):
            self.control.write_bytes(raw)
            result = self.command('epkg', '-w', self.root / 'work', '-e', self.control, 'fix001')
            self.assertEqual((result.returncode, result.stdout), (1, ''))
            self.assertTrue(result.stderr.startswith('epkg: '))
            self.assertNotIn('Traceback', result.stderr)
            self.assertFalse((self.root / 'work').exists())

    def test_all_installed_interim_operations_remain_unavailable(self):
        output = self.build()
        before = sorted(p.relative_to(self.root) for p in self.root.rglob('*'))
        for args in (('-e', output), ('-pe', output), ('-l',), ('-cv3',),
                     ('-rp', '-L', 'fix001'), ('-r', '-n1'), ('-P', 'sample-bin')):
            with self.subTest(args=args):
                result = self.command('emgr', *args)
                self.assertEqual((result.returncode, result.stdout), (1, ''))
                self.assertIn('not connected', result.stderr)
        self.assertEqual(sorted(p.relative_to(self.root) for p in self.root.rglob('*')), before)

    def test_action_and_selector_ambiguity_rejected(self):
        for args in ([], ['-dr', '-e', 'fix.epkg'], ['-l', '-e', 'fix.epkg'],
                     ['-d', '-e', 'one', 'two'], ['-d'], ['-d', '-p', 'one'],
                     ['-l', '-L', 'fix001', '-n1'], ['-c', '-n0'], ['-lv4'],
                     ['-r'], ['-r', '-L', 'fix001', '-v2'], ['-P', 'one', 'two'],
                     ['-i', 'kernel.epkg'], ['-C', '-L', 'fix001'], ['-X', '-e', 'fix.epkg']):
            with self.subTest(args=args), self.assertRaises(UsageError):
                parse('emgr', args)

    def test_label_length_and_interactive_mode_are_distinct(self):
        self.assertEqual(parse('epkg', ['x' * 100]).action, 'interim-build-interactive')
        for args in ([], ['x' * 101], ['../outside'], ['one', 'two'], ['-e', 'control']):
            with self.subTest(args=args), self.assertRaises(UsageError):
                parse('epkg', args)
        result = self.command('epkg', 'fix001')
        self.assertEqual((result.returncode, result.stdout), (1, ''))
        self.assertFalse((self.root / 'epkgwork').exists())

    def test_display_escapes_terminal_formatting_and_marks_unknown_reboot(self):
        self.manifest['description'] = 'issue\u009b31m\u202ereversed'
        self.manifest['replacements'][0]['activation'] = 'offline-migration'
        output = display(encode(self.manifest, self.artifacts), 2)
        self.assertIn('ABSTRACT: issue\\u009b31m\\u202ereversed\n', output)
        self.assertIn('REBOOT REQUIRED: not established\n', output)


if __name__ == '__main__':
    unittest.main()
