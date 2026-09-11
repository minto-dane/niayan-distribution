#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Verify generated configured roots in a disposable privileged VM filesystem."""
import argparse
from decimal import Decimal
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import tarfile
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('worker', 'target-base', 'inputs', 'report'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    if os.getuid() != 0 or os.geteuid() != 0:
        parser.error('requires a disposable privileged VM')
    expected = json.loads((args.inputs/'report.json').read_text())
    assert expected['result'] == 'pass' and [c['name'] for c in expected['cases']] == ['keep', 'vendor', 'links', 'deleted', 'restored', 'empty']
    results = []
    for case in expected['cases']:
        source = args.inputs/(case['name']+'.tar'); assert source.stat().st_size <= 1024*1024
        data = source.read_bytes(); digest = hashlib.sha256(data).hexdigest(); assert digest == case['archive']
        with tempfile.TemporaryDirectory(prefix='configured-', dir=args.target_base) as temporary:
            parent = Path(temporary); target = parent/'root'; target.mkdir(mode=0o700)
            f = os.open(source, os.O_RDONLY | os.O_CLOEXEC)
            d = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            lease = os.open(parent/'writer.lock', os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                deadline = int(time.clock_gettime(time.CLOCK_BOOTTIME)*1000)+60000
                result = subprocess.run([str(args.worker), digest, str(len(data)), str(case['entries']), str(deadline), str(f), str(d), str(lease)],
                    pass_fds=(f, d, lease), capture_output=True, text=True, timeout=65)
            finally:
                os.close(lease); os.close(d); os.close(f)
            assert result.returncode == 0 and not result.stderr, (case['name'], result)
            assert json.loads(result.stdout) == dict(result='extracted', profile='linux-inode-v1', archive_sha256=digest, entries=case['entries'], published=False)
            names = set(); configured = set()
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
                for item in archive:
                    name = item.name.removeprefix('./').rstrip('/') or '.'
                    assert name not in names
                    path = target/name; actual = path.lstat()
                    if item.islnk():
                        link = item.linkname.removeprefix('./'); assert link in names
                        other = (target/link).lstat()
                        assert (actual.st_ino, actual.st_dev) == (other.st_ino, other.st_dev)
                    else:
                        assert (stat.S_IMODE(actual.st_mode), actual.st_uid, actual.st_gid) == (item.mode, item.uid, item.gid)
                        assert actual.st_mtime_ns == int(Decimal(item.pax_headers.get('mtime', str(item.mtime)))*10**9)
                        if 'atime' in item.pax_headers:
                            assert actual.st_atime_ns == int(Decimal(item.pax_headers['atime'])*10**9)
                        if item.isdir():
                            assert stat.S_ISDIR(actual.st_mode)
                        elif item.issym():
                            assert stat.S_ISLNK(actual.st_mode) and os.readlink(path) == item.linkname
                        else:
                            assert item.isreg() and stat.S_ISREG(actual.st_mode)
                            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC)
                            try:
                                content = bytearray()
                                while chunk := os.read(fd, 65536):
                                    content.extend(chunk)
                                    assert len(content) <= 1024*1024
                                flags, = struct.unpack('@L', fcntl.ioctl(fd, 0x80086601, bytes(struct.calcsize('@L'))))
                            finally:
                                os.close(fd)
                            assert bytes(content) == archive.extractfile(item).read()
                            if name in case['configuration']:
                                want = case['configuration'][name]; configured.add(name)
                                assert hashlib.sha256(content).hexdigest() == want['content'] and len(content) == want['size']
                                assert want['acl'] is None  # This integration fixture has no extended ACL.
                                attrs = {os.fsencode(key).hex(): os.getxattr(path, key, follow_symlinks=False).hex()
                                         for key in os.listxattr(path, follow_symlinks=False)}
                                assert attrs == want['xattrs']
                                assert flags & want['flags'][0] == want['flags'][0] and flags & want['flags'][1] == 0
                    names.add(name)
            actual_names = {'.'} | {str(p.relative_to(target)) for p in target.rglob('*')}
            assert actual_names == names and configured == set(case['configuration']) and len(names) == case['entries']
            if case['name'] == 'deleted':
                assert not (target/'etc/fixture.conf').exists() and (target/'etc/fixture.conf.save').is_file()
            if case['name'] == 'empty':
                assert (target/'etc/fixture.conf').is_file() and (target/'etc/fixture.conf').stat().st_size == 0
            results.append(dict(name=case['name'], archive=digest, entries=len(names), exact_namespace=True,
                original_and_configured_content=True, numeric_permissions_and_times=True, configured_attributes=True, hardlinks=True))
            print('PASS physical configured root', case['name'], flush=True)
    args.report.write_text(json.dumps(dict(result='pass', cases=results, published=False, production_authorization=False,
        actual_boot=False, ctime_birthtime_restored=False), indent=2)+'\n')


if __name__ == '__main__':
    main()
