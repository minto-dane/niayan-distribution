#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Check actual package replacement only inside an explicitly disposable VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

OLD_UNIT = Path('/usr/lib/systemd/system/niaos-root-preparation.service')
NEW_UNIT = Path('/usr/lib/systemd/system/niaos-root-session.service')


def run(*args):
    return subprocess.run(args, capture_output=True, check=True, timeout=60)


def snapshot(path):
    info = path.stat()
    return [info.st_ino, info.st_mode, hashlib.sha256(path.read_bytes()).hexdigest()]


def offline(old, new):
    with tempfile.TemporaryDirectory(prefix='nia-upgrade-offline-') as temporary:
        target = Path(temporary)
        # Only a shell and its real loader/libraries are needed by preinst and
        # postrm during unpack. No host /run, /proc, devices or services are shared.
        shell = Path('/bin/sh').resolve()
        files = [(shell, target/'bin/sh')]
        for token in run('ldd', str(shell)).stdout.decode().split():
            if token.startswith('/'):
                files.append((Path(token), target/token.lstrip('/')))
        for source, destination in files:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        state = target/'var/lib/dpkg'; state.mkdir(parents=True)
        (state/'status').write_text('')
        run('dpkg', '--root='+str(target), '--unpack', str(old))
        obsolete = [target/str(OLD_UNIT).lstrip('/'),
                    target/'usr/lib/systemd/system/niaos-root-preparation.socket',
                    target/'usr/lib/niaos/root-preparation/dev/null']
        assert all(p.exists() for p in obsolete)
        saved = target/'var/lib/niaos/bootstrap.json'; saved.parent.mkdir(parents=True)
        saved.write_bytes(b'opaque existing recovery record\n'); saved.chmod(0o600)
        before = snapshot(saved)
        result = run('dpkg', '--root='+str(target), '--unpack', str(new))
        assert not any(p.exists() for p in obsolete)
        assert (target/str(NEW_UNIT).lstrip('/')).is_file()
        assert before == snapshot(saved)
        bank = (target/'usr/libexec/niaos/root_bank.py').read_text()
        assert 'def serve(' not in bank and 'def connection(' not in bank
        return dict(offline_unpack=True, obsolete_package_files_removed=True,
                    shared_bank_retained=True, recovery_record_unchanged=True,
                    configured_in_chroot=False, stdout=result.stdout.decode())


def live(new):
    paths = [p for p in (OLD_UNIT, NEW_UNIT, Path('/usr/libexec/niaos/root_bank.py'),
        Path('/var/lib/niaos/bootstrap.json'), Path('/var/lib/niaos/core/store/store.lock'),
        Path('/var/lib/niaos/roots/bank.lock')) if p.is_file()]
    before = {str(p): snapshot(p) for p in paths}
    units = ('niaos-root-preparation.service', 'niaos-root-preparation.socket',
             'niaos-root-session.service', 'niaos-root-session.socket')
    properties = lambda: {u: run('systemctl', 'show', u, '-p', 'ActiveState', '-p', 'MainPID').stdout.decode() for u in units}
    prior = properties()
    result = subprocess.run(['dpkg', '--unpack', str(new)], capture_output=True, timeout=60)
    assert result.returncode != 0 and b'upgrade requires an offline target' in result.stderr, result.stderr
    assert before == {str(p): snapshot(p) for p in paths}
    assert prior == properties(), 'package attempt stopped or restarted a service'
    return dict(live_upgrade_refused=True, code_and_storage_unchanged=True,
                unit_states_and_pids_unchanged=True, units=prior, stderr=result.stderr.decode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable-vm', action='store_true', required=True)
    parser.add_argument('--old', type=Path, required=True)
    parser.add_argument('--new', type=Path, required=True)
    parser.add_argument('--mode', choices=('offline', 'live'), required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    assert os.getuid() == os.geteuid() == 0 and Path('/proc/1/comm').read_text().strip() == 'systemd'
    old, new = args.old.resolve(strict=True), args.new.resolve(strict=True)
    result = offline(old, new) if args.mode == 'offline' else live(new)
    args.report.write_text(json.dumps(dict(result='pass', cases=result,
        old_sha256=hashlib.sha256(old.read_bytes()).hexdigest(),
        new_sha256=hashlib.sha256(new.read_bytes()).hexdigest()), indent=2)+'\n')
    print('PASS root controller package replacement:', args.mode)


if __name__ == '__main__':
    main()
