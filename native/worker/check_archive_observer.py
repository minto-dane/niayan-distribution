# SPDX-License-Identifier: BSD-3-Clause
"""Packaged observer acceptance: disposable VM, actual HTTPS and native CAS."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import time

DEST = Path('/opt/nia-observer-test')


def client(output, native_mode=None):
    sys.path.insert(0, '/usr/lib/niaos/archive-observer/native')
    job = json.loads((DEST/'job.json').read_text())
    public = (DEST/'public-key').read_bytes()
    if native_mode:
        store, media = output/'store', output/'media'
        store.mkdir(mode=0o700); media.mkdir(mode=0o700)
        for name in ('original.deb', 'InRelease', 'Packages'):
            shutil.copyfile(DEST/'input'/name, media/name)
        for name in ('control', 'keyring', 'public-key'):
            shutil.copyfile(DEST/name, media/name)
        (media/'scope').write_bytes(bytes.fromhex(job['scope']))
        uid = pwd.getpwnam('nia-supply').pw_uid
        if native_mode == 'wrong-observer-uid':
            uid += 1
        mode = native_mode if native_mode in ('accepted', 'wrong-control') else 'denied'
        subprocess.run([str(DEST/'run_archive_observer_tests'), str(store), str(media), str(uid),
                        job['index'], job['deb'], mode], check=True, timeout=140)
        if native_mode == 'accepted':
            print('PASS packaged observer HTTPS credential native CAS', flush=True)
            return 0
        print('PASS native observer rejection with cleared bindings', flush=True)
        return 2
    from archive_observer_client import observe
    from deb_archive import ar_members, decompress, tar_inventory, MAX_CONTROL
    fds = [os.open(DEST/'input'/name, os.O_RDONLY | os.O_CLOEXEC) for name in ('InRelease', 'Packages', 'original.deb')]
    try:
        try:
            receipt = observe(job, fds, public_key=public)
        except Exception as exc:
            print('REJECTED '+type(exc).__name__, flush=True)
            return 2
        original = (DEST/'input/original.deb').read_bytes()
        control = tar_inventory(decompress(*ar_members(original)[1], MAX_CONTROL), control=True)[1]['control']
        store, media = output/'store', output/'media'
        store.mkdir(mode=0o700); media.mkdir(mode=0o700)
        artifacts = {'receipt': receipt.wire, 'policy': receipt.policy_bytes, 'original.deb': original,
            'control': control, 'InRelease': (DEST/'input/InRelease').read_bytes(),
            'Packages': (DEST/'input/Packages').read_bytes(), 'keyring': (DEST/'keyring').read_bytes(),
            'public-key': public, 'scope': bytes.fromhex(job['scope'])}
        for name, data in artifacts.items():
            (media/name).write_bytes(data)
        subprocess.run([str(DEST/'run_archive_supply_tests'), str(store), str(media), 'external'], check=True, timeout=60)
        print('PASS packaged observer HTTPS credential native CAS', flush=True)
        return 0
    finally:
        for fd in fds:
            os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--client-output', type=Path)
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--native-mode')
    args = parser.parse_args()
    if args.client_output:
        return client(args.client_output, args.native_mode)
    if (os.geteuid() != 0 or Path('/proc/1/comm').read_text().strip() != 'systemd'
            or subprocess.check_output(['systemd-detect-virt']).strip() not in (b'qemu', b'kvm')):
        parser.error('requires a disposable QEMU/systemd VM')
    shutil.copytree(args.runtime, DEST)
    sys.path.insert(0, str(DEST/'distribution/native'))
    import test_archive_receipt as fixtures
    from test_repository_https import HTTPSTests
    from archive_receipt import scope
    from repository import Repository
    from nia_common import canonical, sha
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, PrivateFormat, NoEncryption
    subprocess.run(['useradd', '--system', '--gid', 'nia-pkg', '--no-create-home', '--shell', '/usr/sbin/nologin', 'nia-pkg'], check=True)
    account = pwd.getpwnam('nia-pkg')
    for name in ('niaos-archive-observer.socket', 'niaos-archive-observer.service'):
        active = subprocess.check_output(['systemctl', 'show', '--value', '-p', 'ActiveState', name]).strip()
        assert active == b'inactive', (name, active)
        enabled = subprocess.run(['systemctl', 'is-enabled', name], capture_output=True)
        assert enabled.stdout.strip() in (b'disabled', b'static')
    state = Path('/var/lib/niaos/supply')
    assert not (state/'repository').exists()
    fixtures.ReceiptTests.setUpClass()
    case = fixtures.ReceiptTests(); case.setUp()
    https = HTTPSTests(); https.setUp()
    lease = {'path': None, 'observations': 0, 'failures': []}
    if args.native:
        base_handler = https.server.RequestHandlerClass

        class HeldReservationHandler(base_handler):
            def do_GET(self):
                if lease['path'] is not None:
                    try:
                        fd = os.open(lease['path'], os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
                        try:
                            try:
                                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            except BlockingIOError:
                                lease['observations'] += 1
                            else:
                                lease['failures'].append('CAS writer was not excluded during HTTPS')
                                fcntl.flock(fd, fcntl.LOCK_UN)
                        finally:
                            os.close(fd)
                    except OSError:
                        lease['failures'].append('held CAS lock missing during HTTPS')
                super().do_GET()

        https.server.RequestHandlerClass = HeldReservationHandler
    certificate = Path('/usr/local/share/ca-certificates/nia-observer-test.crt')
    secret = Path('/etc/niaos/credentials/archive-seed')
    results = []
    try:
        https.remote.targets[case.target] = case.policy
        https.remote.publish()
        shutil.copy2(https.certificate, certificate)
        subprocess.run(['update-ca-certificates'], check=True, stdout=subprocess.DEVNULL)
        repo = Repository(state/'repository', sha(https.remote.bootstrap), https.remote.metadata_url, https.remote.targets_url)
        expected_scope = scope(repo, case.target)
        config = dict(schema='org.niaos.archive-observer/v1', root_sha256=sha(https.remote.bootstrap),
            metadata_url=https.remote.metadata_url, targets_url=https.remote.targets_url, public_key=case.public_key.hex(),
            scopes=[dict(scope=expected_scope, target=case.target, codename='trixie', minimum_security_epoch=7,
                         maximum_lifetime_seconds=300)])
        Path('/etc/niaos').mkdir(mode=0o755, exist_ok=True)
        secret.parent.mkdir(mode=0o700)
        secret.write_bytes(case.key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()));secret.chmod(0o600)
        for name, data in [('archive-observer.json', canonical(config)), ('archive-root.json', https.remote.bootstrap),
                           ('archive-keyring.gpg', case.fixture.fixture.keyring)]:
            path = Path('/etc/niaos')/name;path.write_bytes(data);path.chmod(0o644)
        provision = ['systemctl', 'start', 'niaos-archive-observer-provision.service']
        subprocess.run(provision, check=True, timeout=40)
        before = {n: (state/n).stat().st_ino for n in ('bootstrap-intent.json', 'bootstrap-complete.json', 'repository/writer.lock')}
        assert subprocess.run(provision, capture_output=True, timeout=40).returncode != 0
        subprocess.run(['systemctl', 'reset-failed', 'niaos-archive-observer-provision.service'], check=True)
        assert before == {n: (state/n).stat().st_ino for n in before}
        results.append({'case': 'explicit-bootstrap-and-repeat-refusal', 'passed': True})
        (DEST/'job.json').write_bytes(canonical(dict(schema='org.niaos.archive-observer-request/v1', request_id='c'*64,
            scope=expected_scope, index=case.fixture.index, deb=case.fixture.path)))
        (DEST/'public-key').write_bytes(case.public_key)
        (DEST/'keyring').write_bytes(case.fixture.fixture.keyring)
        from deb_archive import ar_members, decompress, tar_inventory, MAX_CONTROL
        (DEST/'control').write_bytes(tar_inventory(decompress(*ar_members(case.fixture.fixture.deb)[1], MAX_CONTROL), control=True)[1]['control'])
        (DEST/'input').mkdir()
        for name, data in [('InRelease', case.fixture.signed), ('Packages', case.fixture.fixture.packed), ('original.deb', case.fixture.fixture.deb)]:
            (DEST/'input'/name).write_bytes(data)
        subprocess.run(['systemctl', 'start', 'niaos-archive-observer.socket'], check=True)

        def run_case(name, *, accepted=False, user='nia-pkg', native_mode=None):
            out = args.report.parent/name;out.mkdir(mode=0o700);os.chown(out, account.pw_uid, account.pw_gid)
            command = ['/usr/bin/python3', '-I', str(DEST/'distribution/native/worker/check_archive_observer.py'), '--client-output', str(out)]
            if args.native:
                command += ['--native-mode', native_mode or ('accepted' if accepted else 'denied')]
            if user != 'root':
                command = ['runuser', '-u', user, '--', *command]
            before_probes = lease['observations']
            lease['path'] = out/'store/store.lock' if args.native else None
            try:
                run = subprocess.run(command, capture_output=True, text=True, timeout=145)
            finally:
                lease['path'] = None
            (args.report.parent/(name+'.log')).write_text(run.stdout+run.stderr)
            assert run.returncode == (0 if accepted else 2), (name, run.returncode, run.stdout, run.stderr)
            assert ('PASS packaged observer' in run.stdout) == accepted
            assert not lease['failures'], lease['failures']
            if args.native and accepted:
                assert lease['observations'] > before_probes, 'no live CAS reservation observation'
            deadline = time.monotonic()+15
            while subprocess.check_output(['systemctl', 'show', '--value', '-p', 'ActiveState', 'niaos-archive-observer.service']).strip() not in (b'inactive', b'failed'):
                if time.monotonic() > deadline:
                    raise TimeoutError('observer did not exit after one request')
                time.sleep(0.1)
            results.append({'case': name, 'passed': True, 'client_exit': run.returncode,
                            'cas_exclusion_observations': lease['observations']-before_probes})

        run_case('accepted', accepted=True)
        run_case('second-request', accepted=True)
        if args.native:
            run_case('wrong-control', native_mode='wrong-control')
            run_case('wrong-observer-uid', native_mode='wrong-observer-uid')
        state.chmod(0o755)
        run_case('nonprivate-state')
        assert state.stat().st_mode & 0o777 == 0o755
        state.chmod(0o700)
        supply = pwd.getpwnam('nia-supply')
        os.chown(state, 0, 0)
        run_case('wrong-state-owner')
        assert state.stat().st_uid == 0
        os.chown(state, supply.pw_uid, supply.pw_gid)
        run_case('root-peer', user='root')
        original = DEST/'input/original.deb'; original.write_bytes(b'changed')
        run_case('changed-original'); original.write_bytes(case.fixture.fixture.deb)
        path = Path('/etc/niaos/archive-observer.json');path.chmod(0o666)
        run_case('unprotected-config');path.chmod(0o644)
        secret.write_bytes(Ed25519PrivateKey.generate().private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
        run_case('wrong-credential')
        secret.write_bytes(case.key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
        certificate.unlink()
        subprocess.run(['update-ca-certificates', '--fresh'], check=True, stdout=subprocess.DEVNULL)
        run_case('untrusted-https')
        lock = state/'repository/writer.lock';saved = state/'saved-lock';lock.rename(saved)
        try:
            assert subprocess.run(['systemctl', 'start', 'niaos-archive-observer.service'], capture_output=True, timeout=10).returncode != 0
            assert not lock.exists()
        finally:
            saved.rename(lock)
        assert before == {n: (state/n).stat().st_ino for n in before}
        results.append({'case': 'missing-lock-refused-without-reinitialization', 'passed': True})
        args.report.write_text(json.dumps({'schema': 'org.niaos.archive-observer-vm-test/v1', 'result': 'pass',
            'cases': results, 'https_transport': 'real TLS with VM-local temporary CA; default production fetcher',
            'observer_uid': pwd.getpwnam('nia-supply').pw_uid, 'core_uid': account.pw_uid,
            'native_cas_observer': args.native, 'cas_exclusion_observations': lease['observations'],
            'production_authorization': False}, indent=2)+'\n')
    finally:
        subprocess.run(['systemctl', 'stop', 'niaos-archive-observer.socket', 'niaos-archive-observer.service'], check=False)
        subprocess.run(['journalctl', '--sync'], check=False)
        journal = subprocess.check_output(['journalctl', '--no-pager', '-o', 'cat', '-u', 'niaos-archive-observer.service', '-u', 'niaos-archive-observer-provision.service'])
        (args.report.parent/'observer-journal.log').write_bytes(journal)
        if secret.exists(): secret.unlink()
        https.tearDown();case.doCleanups();fixtures.ReceiptTests.tearDownClass()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
