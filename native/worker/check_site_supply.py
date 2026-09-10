#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Root-owned policy fixtures in a disposable systemd VM; never the host."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import selectors
import shutil
import struct
import subprocess
import time

BASE = Path('/etc/niaos/site-supply-test')
POLICY = BASE / 'policy'
FLOOR = BASE / 'floor'
KEY = bytes.fromhex('8a88e3dd7409f195fd52db2d3cba5d72ca6709bf1d94121bf3748801b40f6f5c')
ROOT = bytes([31]) * 16
ENV = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'}


def wire(*, serial=7, start=None, expires=None, key=KEY, epoch=7, count=1, root=ROOT):
    now = int(time.time())
    return (b'NIATRST1' + root + struct.pack('>QQQQ', serial, start or now - 60, expires or now + 1800, count)
            + (bytes([71]) * 32 + key + struct.pack('>QQ', epoch, 600)) * min(count, 1))


def write(path, data):
    # Test-only administrator update of fixed files; production reader never writes.
    temporary = path.with_name(path.name + '.new')
    with temporary.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fchmod(stream.fileno(), 0o644)
        os.fsync(stream.fileno())
    temporary.replace(path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def configure(raw=None, *, serial=7, utc=None, pinned=None):
    raw = wire() if raw is None else raw
    write(POLICY / 'supply.bin', raw)
    write(FLOOR / 'supply.floor', b'NIAFLOR1' + ROOT + struct.pack('>QQ', serial, utc or int(time.time()) - 60)
          + (pinned or hashlib.sha256(raw).digest()))


def snapshot():
    return {str(p): [p.lstat().st_ino, p.lstat().st_mode, p.lstat().st_uid,
                     hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None]
            for p in (POLICY, FLOOR, POLICY / 'supply.bin', FLOOR / 'supply.floor') if p.exists()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() or Path('/proc/1/comm').read_text().strip() != 'systemd':
        parser.error('requires root in a disposable systemd VM')
    account = pwd.getpwnam('nia-pkg')
    assert account.pw_uid > 0
    BASE.mkdir(mode=0o755); POLICY.mkdir(mode=0o755); FLOOR.mkdir(mode=0o755)
    observer = '/usr/libexec/nia/pkg_supply_observe'
    bindings = [ROOT.hex(), (bytes([32]) * 16).hex(), *((bytes([n]) * 32).hex() for n in (33, 34, 35))]
    cases = []

    def probe(label, *, accepted=False, policy=POLICY, root=False):
        before = snapshot()
        result = subprocess.run([observer, str(policy), str(FLOOR), *bindings],
            user=0 if root else account.pw_uid, group=0 if root else account.pw_gid, extra_groups=[],
            env=ENV, capture_output=True, timeout=8)
        assert (result.returncode == 0) == accepted, (label, result.stdout, result.stderr)
        assert snapshot() == before, 'observation mutated persistent policy'
        if accepted:
            assert b'execution_permit=false\n' in result.stdout
        cases.append({'case': label, 'exit': result.returncode, 'stdout': result.stdout.decode()})

    configure(); probe('protected-current-policy', accepted=True)
    probe('root-provider-refused', root=True)
    changes = [
        ('wrong-pinned-hash', {}, {'pinned': bytes([9]) * 32}),
        ('serial-below-floor', {}, {'serial': 8}),
        ('clock-below-floor', {}, {'utc': int(time.time()) + 600}),
        ('policy-expired', {'expires': int(time.time()) - 1}, {}),
        ('policy-not-yet-valid', {'start': int(time.time()) + 600}, {}),
        ('wrong-root', {'root': bytes([30]) * 16}, {}),
        ('excess-authorities', {'count': 257}, {}),
        ('zero-key', {'key': bytes(32)}, {}),
        ('zero-epoch', {'epoch': 0}, {}),
    ]
    for label, policy_args, floor_args in changes:
        configure(wire(**policy_args), **floor_args); probe(label)
    configure(wire() + b'\0'); probe('extra-policy-byte')
    configure()
    for path in (POLICY / 'supply.bin', FLOOR / 'supply.floor'):
        path.chmod(0o666)
        try: probe('writable-' + path.name)
        finally: path.chmod(0o644)
        os.chown(path, account.pw_uid, account.pw_gid)
        try: probe('caller-owned-' + path.name)
        finally: os.chown(path, 0, 0)
    os.chown(POLICY, account.pw_uid, account.pw_gid)
    try: probe('caller-owned-directory')
    finally: os.chown(POLICY, 0, 0)
    saved = FLOOR / 'held'
    (FLOOR / 'supply.floor').rename(saved)
    try: probe('missing-floor')
    finally: saved.rename(FLOOR / 'supply.floor')
    alias = BASE / 'alias'; alias.symlink_to(POLICY, target_is_directory=True)
    try: probe('linked-directory', policy=alias)
    finally: alias.unlink()
    unprotected = Path('/var/tmp/nia-site-unprotected')
    unprotected.mkdir(mode=0o755); shutil.copy2(POLICY / 'supply.bin', unprotected / 'supply.bin')
    try: probe('writable-ancestor', policy=unprotected)
    finally: (unprotected / 'supply.bin').unlink(); unprotected.rmdir()
    # Real session invalidation after a root-authorized atomic policy update.
    sessions = []
    for change in ('policy', 'floor', 'missing'):
        configure()
        command = [str(args.runtime / 'session-driver'), str(POLICY), str(FLOOR), 'wait']
        child = subprocess.Popen(command, user=account.pw_uid, group=account.pw_gid, extra_groups=[],
            env=ENV, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                assert selector.select(10), 'session readiness timeout'
                assert child.stdout.readline() == b'READY\n'
            if change == 'policy': configure(wire(serial=8), serial=8)
            elif change == 'floor': write(FLOOR / 'supply.floor', (FLOOR / 'supply.floor').read_bytes()[:-1] + bytes([(FLOOR / 'supply.floor').read_bytes()[-1] ^ 1]))
            else: (FLOOR / 'supply.floor').unlink()
            output, _ = child.communicate(b'changed\n', timeout=10)
            assert child.returncode == 0, output
            sessions.append({'change': change, 'result': output.decode()})
        finally:
            if child.poll() is None: child.kill(); child.wait()
    # Exercise the actual publication gate while it owns the CAS reservation.
    # All OTHER authorization/health/effect providers remain explicit fixtures.
    publications = []
    Path('/var/lib/niaos').mkdir(mode=0o755, exist_ok=True)
    for label, raw, mode in [('accepted', wire(), 'site-supply'),
                             ('key-change', wire(key=bytes([3]) * 32), 'site-refusal'),
                             ('epoch-change', wire(epoch=8), 'site-refusal')]:
        configure(raw)
        base = Path('/var/lib/niaos') / ('site-publication-' + label)
        base.mkdir(mode=0o700); os.chown(base, account.pw_uid, account.pw_gid)
        for name in ('root', 'state', 'store', 'bank'):
            path = base / name; path.mkdir(mode=0o700); os.chown(path, account.pw_uid, account.pw_gid)
        log = args.report.parent / (label + '.log')
        with log.open('wb') as stream:
            result = subprocess.run([str(args.runtime / 'publication-driver'),
                *(str(base / n) for n in ('root', 'state', 'store', 'bank')),
                str(args.runtime / 'fixtures'), mode, str(POLICY), str(FLOOR)],
                user=account.pw_uid, group=account.pw_gid, extra_groups=[], env=ENV,
                stdout=stream, stderr=subprocess.STDOUT, timeout=180)
        assert result.returncode == 0, log.read_text()[-2048:]
        publications.append({'case': label, 'exit': result.returncode, 'log': log.name})
    args.report.write_text(json.dumps({'format': 1, 'result': 'pass', 'uid': account.pw_uid,
        'probe_cases': cases, 'session_changes': sessions, 'publication_cases': publications,
        'production_managed_authorization': False, 'boot_switch': False,
        'hardware_rollback_resistance': False, 'keys': 'public deterministic test key; never deployment authority'}, indent=2) + '\n')


if __name__ == '__main__':
    main()
