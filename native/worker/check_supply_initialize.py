#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Real native reader and supply provisioning in an owned disposable VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import signal
import struct
import subprocess
import sys
import time

sys.path.insert(0, '/usr/libexec/niaos')
import supply_initialize as installer

ROOT = '1f'*16
REQUEST = '20'*16
WORK = Path('/etc/niaos/supply-provision-test')
INPUT = WORK/'inputs'


def payload(expired=False):
    now = int(time.time())
    policy = (b'NIATRST1' + bytes.fromhex(ROOT) + struct.pack('>QQQQ', 7, now-60,
              now-1 if expired else now+1800, 1) + bytes([71])*32 +
              bytes.fromhex('8a88e3dd7409f195fd52db2d3cba5d72ca6709bf1d94121bf3748801b40f6f5c') +
              struct.pack('>QQ', 7, 600))
    floor = b'NIAFLOR1'+bytes.fromhex(ROOT)+struct.pack('>QQ', 7, now-60)+hashlib.sha256(policy).digest()
    return policy, floor


def bindings(case):
    if case == 'success':
        return Path('/var/lib/niaos'), Path('/etc/niaos')
    return Path('/var/lib/niaos/supply-provision-test')/case, WORK/case


def snapshot(base, config):
    return {str(p): dict(inode=p.stat().st_ino, mode=p.stat().st_mode, links=p.stat().st_nlink,
                        sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            for root in (base, config) for p in root.rglob('*') if p.is_file()}


def child(case):
    base, config = bindings(case)
    installer.BASE, installer.CONFIG = str(base), str(config)
    original = installer.publish

    def publish(source, destination, name):
        if name == 'supply.floor':
            if case == 'kill-before-floor':
                os.kill(os.getpid(), signal.SIGKILL)
            if case == 'kill-linked-floor':
                os.link(name, name, src_dir_fd=source, dst_dir_fd=destination, follow_symlinks=False)
                os.fsync(destination)
                os.kill(os.getpid(), signal.SIGKILL)
        original(source, destination, name)
        if name == 'supply.floor' and case == 'kill-committed-floor':
            os.kill(os.getpid(), signal.SIGKILL)

    if case.startswith('kill-'):
        installer.publish = publish
    installer.initialize(str(INPUT/(case+'.bin')), str(INPUT/(case+'.floor')), ROOT, REQUEST)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--child', choices=('bad-floor', 'expired', 'kill-before-floor',
                                          'kill-linked-floor', 'kill-committed-floor'))
    args = parser.parse_args()
    assert __debug__ and os.getuid() == os.geteuid() == 0
    assert subprocess.check_output(['systemd-detect-virt'], timeout=5).strip() in (b'kvm', b'qemu')
    if args.child:
        child(args.child)
        return
    assert args.report is not None
    WORK.mkdir(mode=0o755)
    INPUT.mkdir(mode=0o755)
    Path('/var/lib/niaos').mkdir(mode=0o755, exist_ok=True)
    Path('/var/lib/niaos/supply-provision-test').mkdir(mode=0o755)
    cases = []
    for case in ('success', 'bad-floor', 'expired', 'kill-before-floor', 'kill-linked-floor', 'kill-committed-floor'):
        base, config = bindings(case)
        if case != 'success':
            base.mkdir(mode=0o755)
            config.mkdir(mode=0o755)
        policy, floor = payload(case == 'expired')
        if case == 'bad-floor':
            floor = floor[:-1] + bytes([floor[-1] ^ 1])
        for suffix, raw in (('.bin', policy), ('.floor', floor)):
            target = INPUT/(case+suffix)
            target.write_bytes(raw)
            target.chmod(0o444)
        command = (['/usr/bin/python3', '-I', '/usr/libexec/niaos/supply_initialize.py', '--initialize',
                    str(INPUT/(case+'.bin')), str(INPUT/(case+'.floor')), ROOT, REQUEST]
                   if case == 'success' else ['/usr/bin/python3', str(Path(__file__).resolve()), '--child', case])
        result = subprocess.run(command, capture_output=True, timeout=25)
        if case == 'success':
            assert result.returncode == 0, result.stderr
            assert (base/installer.COMPLETE).is_file()
        elif case.startswith('kill-'):
            assert result.returncode == -signal.SIGKILL, result.stderr
            assert not (base/installer.COMPLETE).exists()
        else:
            assert result.returncode != 0, result.stdout
            assert not (base/installer.COMPLETE).exists()
        assert (base/installer.ATTEMPT).is_file()
        account = pwd.getpwnam('nia-pkg')
        observed = subprocess.run(['/usr/libexec/nia/pkg_supply_observe', '--planning',
                                  str(config/'supply'), str(base/'trust'), ROOT, REQUEST],
                                  user=account.pw_uid, group=account.pw_gid, extra_groups=[],
                                  capture_output=True, timeout=8)
        # A fully published pair may be readable after an unacknowledged crash.
        # Neither the reader nor the installer calls that non-execution/rollback.
        assert (observed.returncode == 0) == (case in ('success', 'kill-committed-floor')), observed.stdout
        if case == 'kill-linked-floor':
            assert (base/'trust/supply.floor').stat().st_nlink == 2
        if case == 'kill-before-floor':
            assert (config/'supply/supply.bin').is_file() and not (base/'trust/supply.floor').exists()
        before = snapshot(base, config)
        retry = subprocess.run(command, capture_output=True, timeout=10)
        assert retry.returncode != 0 and snapshot(base, config) == before
        cases.append(dict(case=case, exit=result.returncode, native_observer_exit=observed.returncode,
                          retry_refused=True, state_preserved=True, stderr=result.stderr.decode('utf-8', errors='replace')[-1024:]))
    account = pwd.getpwnam('nia-pkg')
    denied = subprocess.run(['/usr/bin/python3', '-I', '/usr/libexec/niaos/supply_initialize.py',
                             '--initialize', str(INPUT/'success.bin'), str(INPUT/'success.floor'), ROOT, REQUEST],
                            user=account.pw_uid, group=account.pw_gid, extra_groups=[], capture_output=True, timeout=5)
    assert denied.returncode != 0 and b'installer-root-required' in denied.stderr
    args.report.write_text(json.dumps(dict(result='pass', cases=cases, nonroot_installer_refused=True,
        fixture_public_key_only=True, production_keys_provisioned=False, real_power_loss_tested=False,
        whole_runtime_proof=False), indent=2)+'\n')


if __name__ == '__main__':
    main()
