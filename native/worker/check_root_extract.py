#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Privileged worker acceptance in explicitly supplied disposable nodev storage."""
import argparse
import hashlib
import fcntl
import io
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import tarfile
import tempfile
import time


def archive():
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.PAX_FORMAT) as writer:
        def entry(name, kind=tarfile.REGTYPE, mode=0o640, uid=42, gid=43,
                  content=b'', link='', pax=None, major=0, minor=0):
            item = tarfile.TarInfo(name)
            item.type, item.mode, item.uid, item.gid = kind, mode, uid, gid
            item.mtime, item.linkname = 1700000000, link
            item.devmajor, item.devminor = major, minor
            item.pax_headers = pax or {}
            item.size = len(content) if kind == tarfile.REGTYPE else 0
            writer.addfile(item, io.BytesIO(content) if item.size else None)
        entry('.', tarfile.DIRTYPE, 0o755, 0, 0)
        entry('etc', tarfile.DIRTYPE, 0o2750)
        entry('etc/value', content=b'value\x00\xff', pax={
            'mtime': '1700000000.000000007', 'atime': '1700000001.000000009',
            'SCHILY.xattr.user.demo': 'value',
            'SCHILY.acl.access': 'user::rw-,user:44:r--,group::r--,mask::r--,other::---'})
        entry('sym', tarfile.SYMTYPE, 0o777, link='etc/value')
        entry('alias', tarfile.LNKTYPE, link='etc/value')
        entry('fifo', tarfile.FIFOTYPE, 0o600)
        entry('character', tarfile.CHRTYPE, 0o600, major=1, minor=3)
        entry('block', tarfile.BLKTYPE, 0o600, major=8, minor=1)
        entry('日本語', content=b'utf8')
        entry('raw-\udcff', content=b'bytes')
    return stream.getvalue(), 10


def run(worker, base, raw, count, *, digest=None, deadline=None, occupied=False, writable=False):
    # No production socket, device path or installed state is used.
    with tempfile.TemporaryDirectory(prefix='root-extract-', dir=base) as work:
        parent = Path(work)
        target = parent / 'root'
        target.mkdir(mode=0o700)
        if occupied:
            (target / 'existing').write_bytes(b'preserve')
        source = parent / 'input.tar'
        source.write_bytes(raw)
        f = os.open(source, os.O_RDWR if writable else os.O_RDONLY)
        d = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        lease = os.open(parent / 'writer.lock', os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            # Keep the worker's fixed descriptor protocol explicit; no preexec
            # callbacks or shell interpolation in a privileged launcher.
            until = deadline if deadline is not None else int(time.clock_gettime(time.CLOCK_BOOTTIME) * 1000) + 60000
            result = subprocess.run([str(worker), digest or hashlib.sha256(raw).hexdigest(),
                str(len(raw)), str(count), str(until), str(f), str(d), str(lease)], pass_fds=(f, d, lease),
                capture_output=True, text=True, timeout=65, check=False)
        finally:
            os.close(lease)
            os.close(d)
            os.close(f)
        record = dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        if result.returncode == 0:
            receipt = json.loads(result.stdout)
            assert receipt == dict(result='extracted', profile='linux-inode-v1',
                archive_sha256=hashlib.sha256(raw).hexdigest(), entries=count, published=False)
            value = target / 'etc/value'
            # Capture times before the independent Python read changes atime.
            info = value.stat()
            assert (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (42, 43, 0o640)
            assert (info.st_mtime_ns, info.st_atime_ns) == (1700000000000000007, 1700000001000000009)
            assert value.read_bytes() == b'value\x00\xff'
            assert os.getxattr(value, 'user.demo') == b'value'
            assert os.getxattr(value, 'system.posix_acl_access')
            assert (target / 'alias').stat().st_ino == info.st_ino
            assert os.readlink(target / 'sym') == 'etc/value'
            assert stat.S_ISFIFO((target / 'fifo').lstat().st_mode)
            char = (target / 'character').lstat()
            block = (target / 'block').lstat()
            assert stat.S_ISCHR(char.st_mode) and (os.major(char.st_rdev), os.minor(char.st_rdev)) == (1, 3)
            assert stat.S_ISBLK(block.st_mode) and (os.major(block.st_rdev), os.minor(block.st_rdev)) == (8, 1)
            assert (target / '日本語').read_bytes() == b'utf8'
            assert (target / 'raw-\udcff').read_bytes() == b'bytes'
            assert target.stat().st_mtime_ns == 1700000000000000000
            # Device nodes are observed with lstat only; never opened.
            record['independent_filesystem_check'] = 'pass'
        else:
            assert not result.stdout, record
            assert json.loads(result.stderr)['result'] == 'failed', record
        if occupied:
            assert (target / 'existing').read_bytes() == b'preserve'
        return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', required=True, type=Path)
    parser.add_argument('--target-base', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    if os.getuid() != 0 or os.geteuid() != 0:
        parser.error('requires a disposable privileged container and explicit target base')
    raw, count = archive()
    cases = {}
    cases['full-linux-root'] = run(args.worker, args.target_base, raw, count)
    assert cases['full-linux-root']['returncode'] == 0, cases['full-linux-root']
    for name, changes in [('wrong-hash', dict(digest='0' * 64)),
            ('wrong-count', dict(count=count + 1)), ('expired', dict(deadline=0)),
            ('occupied-target', dict(occupied=True)), ('writable-input', dict(writable=True))]:
        options = dict(count=count)
        options.update(changes)
        cases[name] = run(args.worker, args.target_base, raw, **options)
        assert cases[name]['returncode'] != 0, name
    args.report.write_text(json.dumps(dict(result='pass', cases=cases,
        production_authorization=False, actual_boot=False), indent=2) + '\n')
    print('PASS root extraction: full filesystem observation and five refusal cases')


if __name__ == '__main__':
    main()
