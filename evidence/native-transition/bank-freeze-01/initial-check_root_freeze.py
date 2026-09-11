#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Dedicated disposable ext4 bank: kernel read-only transition and reinspection."""
import argparse
import errno
import fcntl
import hashlib
import json
import mmap
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from root_bank import Bank, Rejected, mount_identity, provision_bank
from root_freeze import FrozenRoot, filesystem
from check_root_extract import archive
from check_root_reinspection import snapshot


def mount_binding(fd):
    info = os.fstat(fd)
    return dict(mount_id=mount_identity(fd), inode=info.st_ino,
                device_major=os.major(info.st_dev), device_minor=os.minor(info.st_dev))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', type=Path, required=True)
    parser.add_argument('--bank', type=Path, required=True, help='empty dedicated disposable ext4 filesystem root')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    assert os.getuid() == os.geteuid() == 0
    results = {}
    with tempfile.TemporaryDirectory(prefix='freeze-cas-') as temporary:
        base = Path(temporary); base.chmod(0o711)
        source = base/'root.tar'; raw, count = archive(); source.write_bytes(raw); source.chmod(0o444)
        lock = base/'store.lock'; lock.touch(mode=0o600); os.chown(lock, 1000, 1000)
        source_fd = os.open(source, os.O_RDONLY); lease = os.open(lock, os.O_RDWR)
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        provision_bank(args.bank)
        bank = Bank(args.bank, lock, args.worker, 1000); freeze = FrozenRoot()
        alias = base/'alias'; alias.mkdir(); child_source = base/'child-source'; child_source.mkdir()
        alias_mounted = child_mounted = False
        try:
            request = dict(version=1, stage='1'*32, generation='2'*64, root_manifest='3'*64,
                           archive=hashlib.sha256(raw).hexdigest(), size=len(raw), entries=count,
                           deadline_ms=int(time.clock_gettime(time.CLOCK_BOOTTIME)*1000)+60000)
            assert bank.prepare(request, source_fd, lease)['state'] == 'extracted'
            expected = mount_binding(bank.directory); target = args.bank/request['stage']/'root'
            records = [(args.bank/request['stage']/n).read_bytes() for n in ('intent.json', 'result.json')]
            try: freeze.acquire(bank, request, source_fd, lease, dict(expected, mount_id=expected['mount_id']+1))
            except Rejected: results['wrong-bank-refused'] = True
            else: raise AssertionError('wrong bank accepted')
            subtree = args.bank/'subtree'; subtree.mkdir(mode=0o700); fd = os.open(subtree, os.O_RDONLY | os.O_DIRECTORY)
            try:
                try: filesystem(fd, mount_binding(fd))
                except Rejected: results['shared-subtree-refused'] = True
                else: raise AssertionError('subtree accepted as dedicated filesystem')
            finally: os.close(fd); subtree.rmdir()
            child = args.bank/'child'; child.mkdir(mode=0o700)
            subprocess.run(['mount', '--bind', str(child_source), str(child)], check=True); child_mounted = True
            try:
                try: freeze.acquire(bank, request, source_fd, lease, expected)
                except Rejected: results['child-mount-refused'] = True
                else: raise AssertionError('child mount accepted')
            finally:
                subprocess.run(['umount', str(child)], check=True); child_mounted = False; child.rmdir()
            subprocess.run(['mount', '--bind', str(args.bank), str(alias)], check=True); alias_mounted = True
            for mapping in (False, True):
                writer = os.open(target/'etc/value', os.O_RDWR)
                view = None
                if mapping:
                    view = mmap.mmap(writer, 0, access=mmap.ACCESS_WRITE); os.close(writer); writer = -1
                try:
                    try: freeze.acquire(bank, request, source_fd, lease, expected)
                    except OSError as exc: assert exc.errno == errno.EBUSY, exc
                    else: raise AssertionError('outstanding writer allowed a read-only transition')
                    assert not filesystem(bank.directory, expected)[1]
                    assert not freeze.ready
                    results['writable-mapping-refused' if mapping else 'writable-fd-refused'] = True
                finally:
                    if view is not None: view.close()
                    if writer >= 0: os.close(writer)
            freeze.acquire(bank, request, source_fd, lease, expected)
            observation = freeze.observe(source_fd, lease)
            assert observation['original_deadline_ms'] == request['deadline_ms']
            assert observation['root']['mount_id'] == expected['mount_id']
            assert observation['root']['inode'] == target.stat().st_ino
            results['frozen-observation'] = observation
            before = snapshot(target)
            for path in (target/'etc/value', alias/request['stage']/'root/etc/value'):
                try: fd = os.open(path, os.O_WRONLY)
                except OSError as exc: assert exc.errno == errno.EROFS, exc
                else: os.close(fd); raise AssertionError('filesystem still writable through an alias')
            results['all-mount-views-readonly'] = True
            assert bank.verify(request, source_fd, lease)['physical_revalidation']
            assert snapshot(target) == before
            assert [(args.bank/request['stage']/n).read_bytes() for n in ('intent.json', 'result.json')] == records
            try: Bank(args.bank, lock, args.worker, 1000)
            except BlockingIOError: results['readonly-bank-lock-retained'] = True
            else: raise AssertionError('second bank acquired reservation')
            freeze.close(); freeze.close()
            assert filesystem(bank.directory, expected)[1]
            try: freeze.observe(source_fd, lease)
            except Rejected: results['close-invalidates-without-thaw'] = True
            else: raise AssertionError('closed observation accepted')
            bank.close(); bank = Bank(args.bank, lock, args.worker, 1000)
            assert bank.inspect(request['stage'])['state'] == 'extracted'
            freeze.acquire(bank, request, source_fd, lease, expected)
            assert bank.verify(request, source_fd, lease)['physical_revalidation']
            results['readonly-restart-and-reinspection'] = True
            # Explicit privileged fault on this disposable volume, never cleanup
            # behavior of FrozenRoot. Observation must detect controller drift.
            subprocess.run(['mount', '-o', 'remount,rw,nodev,nosuid,noexec', str(args.bank)], check=True)
            try: freeze.observe(source_fd, lease)
            except Rejected: results['privileged-remount-change-refused'] = True
            else: raise AssertionError('changed writable filesystem accepted')
        finally:
            freeze.close(); bank.close()
            if child_mounted: subprocess.run(['umount', str(args.bank/'child')], check=True)
            if alias_mounted: subprocess.run(['umount', str(alias)], check=True)
            os.close(source_fd); os.close(lease)
    args.report.write_text(json.dumps(dict(result='pass',cases=results,host_or_active_root_changed=False,
                                         site_authorization=False),indent=2)+'\n')
    print('PASS dedicated bank freeze, live writers, alias exclusion, restart and actual reinspection')


if __name__ == '__main__':
    main()
