#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Explicit disposable VM partition: real bootstrap, device guard and reboot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

PLAN = Path('/etc/niaos/root-bank-device.json')
BASE = Path('/var/lib/niaos')
BANK = BASE/'roots'
BOOTSTRAP = ['/usr/bin/python3', '-I', '/usr/libexec/niaos/storage_bootstrap.py']
SERVICE = 'niaos-root-preparation.service'
SOCKET = 'niaos-root-preparation.socket'
GUARD = 'niaos-root-bank-check.service'
MOUNT = 'var-lib-niaos-roots.mount'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, timeout=75, **kwargs)


def write_plan(value):
    PLAN.write_text(json.dumps(value, sort_keys=True)+'\n'); PLAN.chmod(0o600)


def snapshot():
    names = ('bootstrap.json', 'bootstrap-complete.json', 'core/store/store.lock', 'roots/bank.json', 'roots/bank.lock')
    return {n: [ (BASE/n).stat().st_ino, hashlib.sha256((BASE/n).read_bytes()).hexdigest()] for n in names}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', required=True, help='explicit fresh disposable GPT/ext4 partition; never a host disk')
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--after-reboot', action='store_true')
    args = parser.parse_args()
    assert os.geteuid() == 0 and Path('/proc/1/comm').read_text().strip() == 'systemd'
    if args.after_reboot:
        result = json.loads(args.report.read_text())
        assert result['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        run('systemctl', 'start', MOUNT)
        assert os.statvfs(BANK).f_flag & os.ST_RDONLY
        assert snapshot() == result['snapshot']
        observed = json.loads(run(*BOOTSTRAP, '--check-bank').stdout)
        assert observed['status'] == 'bank-device-checked' and observed['readonly']
        run('systemctl', 'start', SOCKET, SERVICE)
        assert run('systemctl', 'show', SERVICE, '--property=ActiveState', '--value').stdout == b'active\n'
        run('systemctl', 'stop', SOCKET, SERVICE)
        original = PLAN.read_bytes()
        plan = json.loads(original); plan['filesystem_uuid'] = '11111111-2222-3333-4444-555555555555'; write_plan(plan)
        try:
            refusal = subprocess.run(['systemctl', 'start', SOCKET, SERVICE], capture_output=True, timeout=60)
            assert refusal.returncode != 0
            assert run('systemctl', 'show', SERVICE, '--property=ActiveState', '--value').stdout != b'active\n'
            assert snapshot() == result['snapshot']
        finally:
            PLAN.write_bytes(original); PLAN.chmod(0o600)
            run('systemctl', 'stop', SOCKET, SERVICE)
            run('systemctl', 'reset-failed', GUARD, SERVICE, SOCKET)
        run(*BOOTSTRAP, '--check-bank')
        # Explicit test-only state fault, followed by restoration of the same
        # inode; neither normal startup nor the installer repairs missing state.
        run('mount', '-o', 'remount,rw,nodev,nosuid,noexec', str(BANK))
        lock = BANK/'bank.lock'; held = BANK/'bank.lock.test-held'; lock.rename(held)
        run('mount', '-o', 'remount,ro,nodev,nosuid,noexec', str(BANK))
        try:
            denied = subprocess.run(BOOTSTRAP+['--check-bank'], capture_output=True, timeout=45)
            assert denied.returncode != 0 and not lock.exists()
        finally:
            run('mount', '-o', 'remount,rw,nodev,nosuid,noexec', str(BANK)); held.rename(lock)
            run('mount', '-o', 'remount,ro,nodev,nosuid,noexec', str(BANK))
        run(*BOOTSTRAP, '--check-bank'); assert snapshot() == result['snapshot']
        result.update(result='pass',reboot_readonly=True,device_guard_activated=True,changed_plan_blocks_service=True,
                      missing_lock_not_recreated=True,after_reboot=observed,restored_original_state=True)
        args.report.write_text(json.dumps(result,indent=2)+'\n'); print('PASS dedicated bank identity, readonly reboot, guard and state refusal');return
    assert not (BASE/'core').exists() and not BANK.exists() and not PLAN.exists()
    missing = subprocess.run(BOOTSTRAP+['--initialize'],capture_output=True,timeout=75)
    assert missing.returncode != 0 and not (BASE/'bootstrap.json').exists()
    probe = run('/usr/sbin/blkid', '--probe', '--output', 'export', args.device).stdout.decode()
    tags = dict(line.split('=',1) for line in probe.splitlines())
    plan = dict(version=1,partition_uuid=tags['PART_ENTRY_UUID'],filesystem_uuid=tags['UUID'],
                size_bytes=int(run('blockdev','--getsize64',args.device).stdout))
    assert tags['TYPE']=='ext4' and tags['PART_ENTRY_SCHEME']=='gpt'
    cases = ['missing-device-plan']
    for field,value in [('filesystem_uuid','11111111-2222-3333-4444-555555555555'),('size_bytes',plan['size_bytes']+512)]:
        write_plan(dict(plan,**{field:value}))
        denied = subprocess.run(BOOTSTRAP+['--initialize'],capture_output=True,timeout=75)
        assert denied.returncode != 0 and not (BASE/'bootstrap.json').exists()
        cases.append('incorrect-'+field)
    write_plan(plan)
    BASE.mkdir(mode=0o755,exist_ok=True)
    for name in ('core','roots','bootstrap.json','bootstrap-complete.json'):
        p=BASE/name
        if name in ('core','roots'):p.mkdir(mode=0o700)
        else:p.write_bytes(b'incomplete fixture\n');p.chmod(0o600)
        before=(p.stat().st_ino,p.stat().st_mode)
        try:
            denied=subprocess.run(BOOTSTRAP+['--initialize'],capture_output=True,timeout=75)
            assert denied.returncode != 0 and before==(p.stat().st_ino,p.stat().st_mode)
        finally:
            if p.is_dir():p.rmdir()
            else:p.unlink()
        cases.append('preexisting-'+name)
    completed=run(*BOOTSTRAP,'--initialize')
    assert json.loads(completed.stdout)['status']=='storage-initialized'
    observed=json.loads(run(*BOOTSTRAP,'--check-bank').stdout)
    assert observed['readonly'] and os.statvfs(BANK).f_flag & os.ST_RDONLY
    saved=snapshot()
    denied=subprocess.run(BOOTSTRAP+['--initialize'],capture_output=True,timeout=75)
    assert denied.returncode!=0 and snapshot()==saved
    assert run('systemctl','show',SERVICE,'--property=ActiveState','--value').stdout==b'inactive\n'
    assert subprocess.run(['systemctl','is-enabled','--quiet',SOCKET]).returncode!=0
    run('systemctl','start',SOCKET,SERVICE)
    properties=run('systemctl','show',SERVICE,'--property=ActiveState','--property=CapabilityBoundingSet').stdout.decode()
    assert 'ActiveState=active' in properties and 'cap_sys_admin' not in properties
    run('systemctl','stop',SOCKET,SERVICE)
    result=dict(result='awaiting-reboot',plan=plan,observed=observed,snapshot=saved,
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),bootstrap_refusal_cases=cases,
                retry_refused=True,service_activated_only_by_test=True,service_properties=properties,
                installer_formats_device=False,boot_switch_tested=False,site_authorization=False)
    args.report.write_text(json.dumps(result,indent=2)+'\n');print('PASS dedicated bank bootstrap; awaiting reboot')


if __name__ == '__main__':main()
