#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Exercise installed units in a disposable systemd VM, never on the host."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import stat
import subprocess
import time


POLICY = Path('/etc/niaos/root-preparation.json')
BANK = Path('/var/lib/niaos/roots')
CORE = Path('/var/lib/niaos/core')
SOCKET = '/run/niaos/root-preparation.sock'
SERVICE = 'niaos-root-preparation.service'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def check_bootstrap_after_reboot(result):
    assert result['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    for filename, expected in result['bootstrap_files'].items():
        path = Path(filename)
        assert [path.stat().st_ino, hashlib.sha256(path.read_bytes()).hexdigest()] == expected
    result['bootstrap_persisted_after_reboot'] = True


def request(uid, gid, stage, expect_failure=False):
    # Use a fresh real account context, not JSON credentials or root's socket.
    code = '''import json,socket,sys
s=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET);s.settimeout(4)
s.connect(sys.argv[1]);s.sendall((json.dumps({'inspect':sys.argv[2]},sort_keys=True,separators=(',',':'))+'\\n').encode())
print(s.recv(4096).decode(),end='')
'''
    result = subprocess.run(['/usr/bin/python3', '-I', '-c', code, SOCKET, stage],
        user=uid, group=gid, extra_groups=[], capture_output=True, timeout=8)
    if expect_failure:
        assert result.returncode != 0 or b'"state":"extracted"' not in result.stdout
        return {'refused_or_disconnected': True}
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert value['state'] == 'extracted' and value['physical_revalidation'] is False and value['published'] is False
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--after-reboot', action='store_true')
    parser.add_argument('--device-plan', type=Path, required=True, help='explicit root-owned GPT/ext4 plan already installed at /etc/niaos/root-bank-device.json')
    args = parser.parse_args()
    if os.getuid() or Path('/proc/1/comm').read_text().strip() != 'systemd':
        parser.error('requires root in a disposable systemd VM')
    assert args.device_plan == Path('/etc/niaos/root-bank-device.json') and args.device_plan.is_file()
    account = pwd.getpwnam('nia-pkg')
    assert account.pw_uid > 0 and account.pw_shell == '/usr/sbin/nologin'
    if args.after_reboot:
        result = json.loads(args.report.read_text())
        check_bootstrap_after_reboot(result)
        result['after_reboot'] = request(account.pw_uid, account.pw_gid, result['stage'])
        # Missing ownership state and policy stay missing on ordinary activation.
        failures = []
        for target in (BANK / 'bank.lock', CORE / 'store/store.lock', POLICY):
            # Quiesce both units so each case tests its own missing prerequisite,
            # not a socket left disabled by the previous activation failure.
            run('systemctl', 'stop', 'niaos-root-preparation.socket', SERVICE)
            held = target.with_name(target.name + '.test-held')
            if target == BANK/'bank.lock': run('mount', '-o', 'remount,rw,nodev,nosuid,noexec', str(BANK))
            target.rename(held)
            try:
                run('systemctl', 'start', 'niaos-root-preparation.socket')
                failed = subprocess.run(['systemctl', 'start', SERVICE], capture_output=True)
                assert failed.returncode != 0
                request(account.pw_uid, account.pw_gid, result['stage'], expect_failure=True)
                assert not target.exists(), str(target)
                failures.append({'missing': str(target), 'activation_exit': failed.returncode,
                                 'diagnostic': failed.stderr.decode()[:2048]})
            finally:
                run('systemctl', 'stop', 'niaos-root-preparation.socket', SERVICE)
                held.rename(target)
                if target == BANK/'bank.lock': run('mount', '-o', 'remount,ro,nodev,nosuid,noexec', str(BANK))
                run('systemctl', 'reset-failed', SERVICE, 'niaos-root-preparation.socket', 'niaos-root-bank-check.service')
                # systemd 257 reset-failed does not clear the socket's separate
                # trigger rate counter. Respect its default two-second window;
                # never disable the production rate limit to make a test pass.
                time.sleep(3)
                run('systemctl', 'start', 'niaos-root-preparation.socket')
            request(account.pw_uid, account.pw_gid, result['stage'])
        result['missing_state_cases'] = failures
        result['missing_state_not_recreated'] = True
        result['after_restoration'] = request(account.pw_uid, account.pw_gid, result['stage'])
        result['result'] = 'pass'
        args.report.write_text(json.dumps(result, indent=2) + '\n')
        return
    assert POLICY.stat().st_uid == 0 and POLICY.stat().st_mode & 0o777 == 0o600
    assert not BANK.exists() and not CORE.exists(), 'installation must not initialize native state'
    assert subprocess.run(['systemctl', 'is-active', '--quiet', SERVICE]).returncode != 0
    assert subprocess.run(['systemctl', 'is-enabled', '--quiet', 'niaos-root-preparation.socket']).returncode != 0
    bootstrap = ['/usr/bin/python3', '-I', '/usr/libexec/niaos/storage_bootstrap.py', '--initialize']
    native = Path('/usr/libexec/nia/pkg_store_bootstrap')
    assert native.is_file(), 'install the component package before explicit bootstrap'
    refusal_cases = []
    # No fixture driver participates in initialization. These are deliberately
    # incomplete installer inputs, confined to this disposable VM.
    held = native.with_name(native.name + '.test-held')
    native.rename(held)
    try:
        denied = subprocess.run(bootstrap, capture_output=True, timeout=70)
        assert denied.returncode != 0 and not CORE.exists() and not BANK.exists()
        refusal_cases.append('missing-native-initializer')
    finally:
        held.rename(native)
    CORE.parent.mkdir(mode=0o755, exist_ok=True)
    for name in ('core', 'roots', 'bootstrap.json', 'bootstrap-complete.json'):
        placeholder = CORE.parent / name
        if name in ('core', 'roots'):
            placeholder.mkdir(mode=0o700)
        else:
            placeholder.write_bytes(b'{"incomplete-test":true}\n'); placeholder.chmod(0o600)
        before = (placeholder.stat().st_ino, placeholder.stat().st_mode)
        try:
            denied = subprocess.run(bootstrap, capture_output=True, timeout=70)
            assert denied.returncode != 0
            assert before == (placeholder.stat().st_ino, placeholder.stat().st_mode)
            assert set(CORE.parent.iterdir()) == {placeholder}
            refusal_cases.append('preexisting-' + name)
        finally:
            if placeholder.is_dir(): placeholder.rmdir()
            else: placeholder.unlink()
    root_refusal = subprocess.run([str(native), 'initialize', str(CORE / 'store')], capture_output=True)
    assert root_refusal.returncode != 0 and b'status=DENIED' in root_refusal.stdout and not CORE.exists()
    refusal_cases.append('native-root-refusal')
    run(*bootstrap)
    intent = CORE.parent / 'bootstrap.json'
    complete = CORE.parent / 'bootstrap-complete.json'
    completion = json.loads(complete.read_text())
    assert completion['intent_sha256'] == hashlib.sha256(intent.read_bytes()).hexdigest()
    assert completion['state'] == 'storage-initialized' and completion['service_activated'] is False
    assert subprocess.run(['systemctl', 'is-active', '--quiet', SERVICE]).returncode != 0
    assert subprocess.run(['systemctl', 'is-active', '--quiet', 'niaos-root-preparation.socket']).returncode != 0
    assert subprocess.run(['systemctl', 'is-enabled', '--quiet', 'niaos-root-preparation.socket']).returncode != 0
    fixed = [intent, complete, CORE / 'store/store.lock', BANK / 'bank.json', BANK / 'bank.lock']
    snapshot = {str(p): (p.stat().st_ino, hashlib.sha256(p.read_bytes()).hexdigest()) for p in fixed}
    denied = subprocess.run(bootstrap, capture_output=True, timeout=70)
    assert denied.returncode != 0
    assert snapshot == {str(p): (p.stat().st_ino, hashlib.sha256(p.read_bytes()).hexdigest()) for p in fixed}
    refusal_cases.append('completed-bootstrap-retry')
    store = CORE / 'store'
    required = os.ST_NODEV | os.ST_NOSUID | os.ST_NOEXEC
    assert os.statvfs(BANK).f_flag & required == required
    # Explicit test controller opens this initialized bank for fixture extraction.
    run('mount', '-o', 'remount,rw,nodev,nosuid,noexec', str(BANK))
    # Fixture authorization is activated only for this test, after real bootstrap.
    run('systemctl', 'enable', '--now', 'niaos-root-preparation.socket')
    worker = Path('/usr/libexec/niaos/root-extract')
    command = [str(args.runtime / 'driver'), str(store), str(args.runtime / 'fixtures'), SOCKET,
        hashlib.sha256(worker.read_bytes()).hexdigest(), 'existing-store']
    with (args.report.parent / 'native-service.log').open('wb') as log:
        run(*command, user=account.pw_uid, group=account.pw_gid, extra_groups=[],
            stdout=log, stderr=subprocess.STDOUT, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'},
            timeout=180)
    stages = [p for p in BANK.iterdir() if p.is_dir()]
    assert len(stages) == 1
    record = request(account.pw_uid, account.pw_gid, stages[0].name)
    props = subprocess.check_output(['systemctl', 'show', SERVICE, '-p', 'MainPID', '-p', 'MemoryMax',
        '-p', 'MemorySwapMax', '-p', 'TasksMax', '-p', 'NoNewPrivileges', '-p', 'CapabilityBoundingSet'], text=True)
    assert 'MemoryMax=1073741824' in props and 'MemorySwapMax=0' in props and 'TasksMax=32' in props
    pid = int(next(line.split('=')[1] for line in props.splitlines() if line.startswith('MainPID=')))
    assert pid > 0
    dev = Path(f'/proc/{pid}/root/dev')
    devices = {p.name: {'mode': p.stat().st_mode, 'rdev': p.stat().st_rdev}
               for p in dev.iterdir()}
    mounts = Path(f'/proc/{pid}/mountinfo').read_text()
    (args.report.parent / 'namespace.json').write_text(json.dumps(
        {'devices': devices, 'mountinfo': mounts, 'service_properties': props}, indent=2) + '\n')
    assert set(devices) == {'null', 'zero', 'random', 'urandom'}, devices
    for name, minor in (('null', 3), ('zero', 5), ('random', 8), ('urandom', 9)):
        assert stat.S_ISCHR(devices[name]['mode']) and devices[name]['rdev'] == os.makedev(1, minor)
    for name in ('dev', 'tmp', 'var/tmp'):
        view = Path(f'/proc/{pid}/root') / name
        assert os.statvfs(view).f_flag & os.ST_RDONLY
        if name != 'dev':
            assert not list(view.iterdir()) and os.statvfs(view).f_flag & os.ST_NODEV
    retry = subprocess.run(['/usr/bin/python3', '-I', '/usr/libexec/niaos/root_bank.py',
        '--config', str(POLICY), '--provision-bank'], capture_output=True)
    assert retry.returncode != 0
    result = {'result': 'awaiting-reboot', 'stage': stages[0].name, 'record': record,
        'uid': account.pw_uid, 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'service_properties': props, 'worker_sha256': hashlib.sha256(worker.read_bytes()).hexdigest(),
        'device_view': devices, 'readonly_temporary_directories': True,
        'automatic_initialization': False, 'automatic_activation': False,
        'production_storage_bootstrap': True, 'bootstrap_completion': completion,
        'bootstrap_refusal_cases': refusal_cases, 'bootstrap_files': snapshot,
        'running_root_switched': False, 'production_admission_policy': False}
    args.report.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
