# SPDX-License-Identifier: BSD-3-Clause
"""Test-only credential deployment in a disposable QEMU/systemd VM.

Temporary observer keys and genuine cryptographic repository fixtures are not
production authorization. Nothing from this helper is installed by a package.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys


def child():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import check_archive_receipt_bridge as bridge
    credential = Path(os.environ['CREDENTIALS_DIRECTORY'])/'archive-seed'
    fd = os.open(credential, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        readonly = bool(os.fstatvfs(fd).f_flag & os.ST_RDONLY)
        print(json.dumps({'credential_uid': info.st_uid, 'observer_uid': os.geteuid(),
                          'credential_gid': info.st_gid,
                          'credential_acl': os.getxattr(fd, 'system.posix_acl_access').hex(),
                          'credential_mode': oct(info.st_mode & 0o7777),
                          'credential_mount_readonly': readonly,
                          'credential_link_count': info.st_nlink}), flush=True)
        if not readonly:
            raise RuntimeError('systemd did not deliver a read-only credential mount')
        sys.argv = [sys.argv[0], '--driver', '/opt/nia-credential-test/run_archive_supply_tests',
                    '--credential-fd', str(fd), '--public-key', '/opt/nia-credential-test/public-key']
        try:
            return bridge.main()
        except subprocess.CalledProcessError as exc:
            if exc.stderr:
                print(exc.stderr.decode(errors='replace'), file=sys.stderr)
            raise
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--child', action='store_true')
    args = parser.parse_args()
    if args.child:
        return child()
    if (os.geteuid() != 0 or Path('/proc/1/comm').read_text().strip() != 'systemd'
            or subprocess.check_output(['systemd-detect-virt']).strip() not in (b'qemu', b'kvm')):
        parser.error('requires root inside a disposable QEMU/systemd VM')
    if args.runtime is None or args.report is None:
        parser.error('runtime and report required')
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, PrivateFormat, NoEncryption
    dest = Path('/opt/nia-credential-test')
    shutil.copytree(args.runtime, dest)
    subprocess.run(['useradd', '--system', '--no-create-home', '--shell', '/usr/sbin/nologin',
                    'nia-supply-test'], check=True)
    uid = pwd.getpwnam('nia-supply-test').pw_uid
    secret = Path('/etc/niaos/archive-credential-test')
    secret.mkdir(mode=0o700, parents=True, exist_ok=False)
    key = Ed25519PrivateKey.generate()
    seed = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    seed_path = secret/'seed'

    def configure(raw, pin):
        seed_path.write_bytes(raw)
        seed_path.chmod(0o600)
        (dest/'public-key').write_bytes(pin)
        (dest/'public-key').chmod(0o644)

    unit = 'nia-archive-credential-test.service'
    unit_path = Path('/run/systemd/system')/unit
    unit_path.write_text('''# SPDX-License-Identifier: BSD-3-Clause
[Unit]
Description=NiaOS disposable archive credential acceptance
[Service]
Type=oneshot
User=nia-supply-test
Group=nia-supply-test
ExecStart=/usr/bin/python3 -I /opt/nia-credential-test/distribution/native/worker/check_archive_credential.py --child
LoadCredential=archive-seed:/etc/niaos/archive-credential-test/seed
UMask=0077
Environment=LC_ALL=C.UTF-8
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
NoNewPrivileges=yes
CapabilityBoundingSet=
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
RestrictNamespaces=yes
RestrictAddressFamilies=AF_UNIX
LockPersonality=yes
MemoryDenyWriteExecute=yes
LimitCORE=0
LimitNOFILE=128
MemoryMax=512M
MemorySwapMax=0
CPUQuota=100%
TasksMax=32
TimeoutStartSec=90
TimeoutStopSec=10
KillMode=control-group
Restart=no
''')
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    cases = []
    try:
        for name, raw, pin, expected in [
                ('accepted', seed, public, None),
                ('wrong-public-key', seed, bytes([1])*32, 'differs from independent key'),
                ('short-credential', seed[:31], public, 'private read-only 32-byte'),
                ('missing-credential', None, public, None)]:
            if raw is None:
                seed_path.unlink()
            else:
                configure(raw, pin)
            cursor_text = subprocess.check_output(['journalctl', '--no-pager', '-n', '0', '--show-cursor']).decode()
            cursor = next(line.removeprefix('-- cursor: ') for line in cursor_text.splitlines()
                          if line.startswith('-- cursor: '))
            run = subprocess.run(['systemctl', 'start', unit], capture_output=True, timeout=110)
            subprocess.run(['journalctl', '--sync'], check=True)
            # A completed oneshot may clear InvocationID. Use the pre-start
            # journal cursor so successful and failed invocations are captured.
            log = subprocess.check_output(['journalctl', '--no-pager', '-o', 'cat',
                                          '--after-cursor='+cursor, '-u', unit]).decode()
            (args.report.parent/(name+'.log')).write_text(log)
            if name == 'accepted':
                assert run.returncode == 0 and log.count('PASS archive receipt bridge ') == 5, log
                assert '"credential_mount_readonly": true' in log
                assert '"observer_uid": '+str(uid) in log
                assert '"credential_uid": 0' in log and '"credential_mode": "0o440"' in log
            else:
                assert run.returncode != 0 and 'PASS archive receipt bridge accepted' not in log
                if expected:
                    assert expected in log, log
            assert seed.hex() not in log
            state = subprocess.check_output(['systemctl', 'show', '--value', '-p', 'ActiveState', unit]).strip()
            assert state in (b'inactive', b'failed')
            cases.append({'case': name, 'passed': True, 'service_exit': run.returncode,
                          'active_state': state.decode()})
            if state == b'failed':
                subprocess.run(['systemctl', 'reset-failed', unit], check=True)
        args.report.write_text(json.dumps({'schema': 'org.niaos.archive-credential-vm-test/v1',
            'result': 'pass', 'observer_uid': uid, 'cases': cases,
            'production_authorization': False, 'repository_transport': 'in-process signed fixture; no HTTPS',
            'private_keys_exported': False}, indent=2)+'\n')
    finally:
        subprocess.run(['systemctl', 'stop', unit], check=False)
        if seed_path.exists():
            seed_path.unlink()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
