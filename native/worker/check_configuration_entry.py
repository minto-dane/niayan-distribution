#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Apply source-checked configuration entries only in an explicitly disposable VM."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import tempfile
import time


def raw_acl(text):
    result = bytearray(struct.pack('<I', 2))
    for entry in text.split(','):
        label, who, bits = entry.split(':')
        tag = {'user': 2 if who else 1, 'group': 8 if who else 4, 'mask': 16, 'other': 32}[label]
        perm = sum(bit for c, bit in zip(bits, (4, 2, 1), strict=True) if c != '-')
        result.extend(struct.pack('<HHI', tag, perm, int(who) if who else 2**32-1))
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('worker', 'target-base', 'inputs', 'report'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    if os.getuid() != 0 or os.geteuid() != 0:
        parser.error('requires a disposable privileged VM')
    expected = json.loads((args.inputs/'report.json').read_text())
    assert expected['result'] == 'pass' and expected['native_payload_read'] is True
    assert [case['name'] for case in expected['cases']] == ['local', 'backup', 'vendor', 'override']
    results = []
    for case in expected['cases']:
        source = args.inputs/(case['name']+'.root.tar')
        assert source.is_file() and source.stat().st_size <= 65536
        data = source.read_bytes(); digest = hashlib.sha256(data).hexdigest()
        assert digest == case['root_archive']
        name = bytes.fromhex(case['path_hex']); assert b'/' not in name and name not in (b'.', b'..')
        with tempfile.TemporaryDirectory(prefix='configuration-', dir=args.target_base) as temporary:
            parent = Path(temporary); target = parent/'root'; target.mkdir(mode=0o700)
            f = os.open(source, os.O_RDONLY | os.O_CLOEXEC)
            d = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            lease = os.open(parent/'writer.lock', os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                deadline = int(time.clock_gettime(time.CLOCK_BOOTTIME)*1000)+60000
                result = subprocess.run([str(args.worker), digest, str(len(data)), '2', str(deadline), str(f), str(d), str(lease)],
                    pass_fds=(f, d, lease), capture_output=True, text=True, timeout=65)
            finally:
                os.close(lease); os.close(d); os.close(f)
            assert result.returncode == 0 and not result.stderr, (case['name'], result)
            assert json.loads(result.stdout) == dict(result='extracted', profile='linux-inode-v1', archive_sha256=digest, entries=2, published=False)
            path = os.fsencode(target)+b'/'+name
            actual = os.stat(path, follow_symlinks=False)
            assert stat.S_ISREG(actual.st_mode) and actual.st_nlink == 1
            assert (stat.S_IMODE(actual.st_mode), actual.st_uid, actual.st_gid, actual.st_size) == tuple(case[k] for k in ('mode', 'uid', 'gid', 'size'))
            assert (actual.st_mtime_ns, actual.st_atime_ns) == tuple(case['clocks'][:2])
            attrs = {os.fsencode(key): os.getxattr(path, key, follow_symlinks=False) for key in os.listxattr(path, follow_symlinks=False)}
            want = {bytes.fromhex(key): bytes.fromhex(value) for key, value in case['xattrs'].items()}
            want[b'system.posix_acl_access'] = raw_acl(case['acl'])
            assert attrs == want, (case['name'], attrs, want)
            fd = os.open(path, os.O_RDONLY | os.O_NOATIME | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                content = os.read(fd, 65536)
                flags, = struct.unpack('@L', fcntl.ioctl(fd, 0x80086601, bytes(struct.calcsize('@L'))))
            finally:
                os.close(fd)
            assert hashlib.sha256(content).hexdigest() == case['content']
            assert flags & ~0x80000 == case['flags'][0] and flags & case['flags'][1] == 0
            results.append(dict(name=case['name'], archive=digest, exact_content=True, numeric_permissions=True,
                                exact_acl_and_xattrs=True, flags=True, signed_nanosecond_mtime_and_atime=True))
            print('PASS physical configuration entry', case['name'], flush=True)
    args.report.write_text(json.dumps(dict(result='pass', cases=results, published=False, production_authorization=False,
        actual_boot=False, ctime_birthtime_restored=False), indent=2)+'\n')


if __name__ == '__main__':
    main()
