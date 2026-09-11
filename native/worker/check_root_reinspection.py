#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Frozen private roots: actual service/worker inspection and bounded faults."""
import argparse
import array
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from root_bank import Bank, Rejected, canonical, provision_bank
from check_root_extract import archive


def snapshot(root):
    result = {}
    for parent, directories, files in os.walk(root, followlinks=False):
        for path in [Path(parent), *(Path(parent) / n for n in files),
                     *(Path(parent) / n for n in directories if (Path(parent) / n).is_symlink())]:
            info = path.lstat()
            value = [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
                     info.st_nlink, info.st_size, info.st_atime_ns, info.st_mtime_ns, info.st_ctime_ns]
            value.append({n: os.getxattr(path, n, follow_symlinks=False).hex()
                          for n in sorted(os.listxattr(path, follow_symlinks=False))})
            if stat.S_ISREG(info.st_mode):
                value.append(hashlib.sha256(path.read_bytes()).hexdigest())
            if stat.S_ISLNK(info.st_mode):
                value.append(os.readlink(path))
            result[os.fsdecode(path.relative_to(root))] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', required=True, type=Path)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    assert os.getuid() == os.geteuid() == 0, 'disposable privileged VM required'
    results = {}
    with tempfile.TemporaryDirectory(prefix='reinspect-', dir=args.base) as temporary:
        base = Path(temporary); base.chmod(0o711)
        store = base/'client'; store.mkdir(mode=0o700); os.chown(store, 1000, 1000)
        lock = store/'cas.lock'; lock.touch(mode=0o600); os.chown(lock, 1000, 1000)
        raw, count = archive(); source = store/'root.tar'; source.write_bytes(raw); source.chmod(0o444)
        bank_path = base/'bank'; bank_path.mkdir(mode=0o700); provision_bank(bank_path)
        bank = Bank(bank_path, lock, args.worker, 1000)
        cases = ('healthy', 'content', 'missing', 'extra', 'xattr', 'mode', 'outside-link', 'symlink', 'child-mount')
        try:
            for number, case in enumerate(cases, 1):
                request = dict(version=1, stage=f'{number:032x}', generation='2'*64, root_manifest='3'*64,
                    archive=hashlib.sha256(raw).hexdigest(), size=len(raw), entries=count,
                    deadline_ms=int(time.clock_gettime(time.CLOCK_BOOTTIME)*1000)+60000)
                source_fd = os.open(source, os.O_RDONLY); lease_fd = os.open(lock, os.O_RDWR)
                fcntl.flock(lease_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                parent = bank_path/request['stage']; target = parent/'root'
                mounted = nested = False
                try:
                    result = bank.prepare(request, source_fd, lease_fd)
                    assert result['state'] == 'extracted', result
                    intent = (parent/'intent.json').read_bytes(); saved_result = (parent/'result.json').read_bytes()
                    if case == 'healthy':
                        try: bank.verify(request, source_fd, lease_fd)
                        except Rejected as exc: assert str(exc) == 'read-only-root'
                        else: raise AssertionError('writable root accepted')
                        results['writable-refused'] = True
                    top = target.stat(); value = (target/'etc/value').stat()
                    if case == 'content':
                        (target/'etc/value').write_bytes(b'broken!')
                        os.utime(target/'etc/value', ns=(value.st_atime_ns, value.st_mtime_ns))
                    elif case == 'missing': (target/'raw-\udcff').unlink()
                    elif case == 'extra': (target/'extra').write_bytes(b'unexpected')
                    elif case == 'xattr': os.setxattr(target/'etc/value', 'user.extra', b'unexpected')
                    elif case == 'mode': (target/'etc/value').chmod(0o600)
                    elif case == 'outside-link': os.link(target/'etc/value', parent/'outside')
                    elif case == 'symlink':
                        link = (target/'sym').lstat(); (target/'sym').unlink(); (target/'sym').symlink_to('different')
                        os.lchown(target/'sym', link.st_uid, link.st_gid)
                        os.utime(target/'sym', ns=(link.st_atime_ns, link.st_mtime_ns), follow_symlinks=False)
                    os.utime(target, ns=(top.st_atime_ns, top.st_mtime_ns))
                    subprocess.run(['mount', '--bind', str(target), str(target)], check=True); mounted = True
                    if case == 'child-mount':
                        subprocess.run(['mount', '--bind', str(target/'etc'), str(target/'etc')], check=True); nested = True
                    subprocess.run(['mount', '-o', 'remount,bind,ro,nodev,nosuid,noexec', str(target)], check=True)
                    # A nested mount is rejected before inspection; snapshotting
                    # its writable view would itself update atime, so freeze it.
                    if nested:
                        subprocess.run(['mount', '-o', 'remount,bind,ro,nodev,nosuid,noexec', str(target/'etc')], check=True)
                    before = snapshot(target)
                    fresh = dict(request, deadline_ms=int(time.clock_gettime(time.CLOCK_BOOTTIME)*1000)+60000)
                    try:
                        observed = bank.verify(fresh, source_fd, lease_fd)
                    except Rejected as exc:
                        assert case != 'healthy', str(exc)
                        results[case] = str(exc)
                    else:
                        assert case == 'healthy', case
                        assert observed['physical_revalidation'] and not observed['published']
                        assert observed['observation']['mount_id'] > 0
                        results[case] = observed
                    assert snapshot(target) == before, 'inspection modified root: '+case
                    assert (parent/'intent.json').read_bytes() == intent and (parent/'result.json').read_bytes() == saved_result
                    assert os.fstat(lease_fd).st_size == 0
                    competing = os.open(lock, os.O_RDWR)
                    try:
                        try: fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except BlockingIOError: pass
                        else: raise AssertionError('inspection released caller lease')
                    finally: os.close(competing)
                    if case == 'healthy':
                        wrong = dict(fresh, generation='4'*64)
                        try: bank.verify(wrong, source_fd, lease_fd)
                        except Rejected as exc: assert str(exc) == 'verification-binding'
                        else: raise AssertionError('different generation accepted')
                        results['wrong-generation-refused'] = True
                        bank.close(); bank = Bank(bank_path, lock, args.worker, 1000)
                        results['restart'] = bank.verify(fresh, source_fd, lease_fd)['physical_revalidation']
                        # Actual authorized socket peer; the parent service owns
                        # its bank reservation while the client drops credentials.
                        os.close(lease_fd); lease_fd = -1
                        address = str(base/'socket')
                        listener = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
                        listener.bind(address); listener.listen(1); os.chown(address, 1000, 1000); os.chmod(address, 0o600)
                        child = os.fork()
                        if child == 0:
                            try:
                                listener.close(); bank.close(); os.close(source_fd)
                                os.setgroups([]); os.setgid(1000); os.setuid(1000)
                                peer = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET); peer.connect(address)
                                a = os.open(source, os.O_RDONLY); lease = os.open(lock, os.O_RDWR)
                                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                                peer.sendmsg([canonical({'verify': fresh})], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [a, lease]))])
                                reply = json.loads(peer.recv(4096)); assert reply['physical_revalidation'] and not reply['published']
                                os._exit(0)
                            except BaseException:
                                import traceback; traceback.print_exc(); os._exit(1)
                        bank.serve(listener, requests=1); listener.close()
                        _, status = os.waitpid(child, 0); assert status == 0
                        results['authorized-fd-rpc'] = True
                        assert snapshot(target) == before
                    print('PASS physical reinspection', case, flush=True)
                finally:
                    if nested: subprocess.run(['umount', str(target/'etc')], check=True)
                    if mounted: subprocess.run(['umount', str(target)], check=True)
                    os.close(source_fd)
                    if lease_fd >= 0: os.close(lease_fd)
        finally: bank.close()
    args.report.write_text(json.dumps(dict(result='pass', cases=results, root_and_records_unchanged=True,
        actual_boot=False, production_authorization=False), indent=2)+'\n')
    print('PASS frozen root reinspection, namespace, metadata, reservation and actual FD RPC')


if __name__ == '__main__':
    main()
