#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Independent wire fixtures for the worker's timestamp cursor; no extraction."""
import argparse
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile


def record(key, value):
    body = b' ' + key.encode('ascii') + b'=' + value.encode('ascii') + b'\n'
    size = len(body) + 1
    while len(str(size)) + len(body) != size:
        size = len(str(size)) + len(body)
    return str(size).encode('ascii') + body


def header(kind=tarfile.REGTYPE, size=0, mtime=0):
    info = tarfile.TarInfo('clock')
    info.type, info.size, info.mtime = kind, size, mtime
    return info.tobuf(format=tarfile.GNU_FORMAT)


def extension(body, kind=tarfile.XHDTYPE):
    return header(kind, len(body)) + body + bytes((-len(body)) % 512)


def archive(fields, mtime=0):
    body = b''.join(record(key, value) for key, value in fields)
    return (extension(body) if body else b'') + header(mtime=mtime) + bytes(1024)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', required=True, type=Path)
    args = parser.parse_args()
    cases = 0
    with tempfile.TemporaryDirectory(prefix='tar-clocks-') as work:
        path = Path(work) / 'input.tar'

        def check(raw, expected=None, expired=False):
            nonlocal cases
            path.write_bytes(raw)
            result = subprocess.run([str(args.driver.resolve()), str(path), 'expired' if expired else 'live'],
                                    capture_output=True, text=True, timeout=15)
            if expected is None:
                assert result.returncode == 1 and not result.stdout, result
            else:
                assert result.returncode == 0, result
                assert json.loads(result.stdout) == expected, (result.stdout, expected)
            cases += 1

        clocks = [('mtime', '-41.876543211'), ('atime', '-0.999999999'),
                  ('ctime', '0.000000042'), ('LIBARCHIVE.creationtime', '123.000000456')]
        check(archive(clocks), [[-42, 123456789], [-1, 1], [0, 42], [123, 456]])
        for value, expected in [('-0', [0, 0]), ('-0.000000001', [-1, 999999999]),
                ('-0.000000000', [0, 0]), ('42.123456789000', [42, 123456789]),
                ('-9223372036854775808', [-9223372036854775808, 0]),
                ('-9223372036854775807.999999999', [-9223372036854775808, 1]),
                ('9223372036854775807.999999999', [9223372036854775807, 999999999])]:
            check(archive([('mtime', value)]), [expected, [0, 0], [0, 0], [0, 0]])
        for integer in [0, -42, 1700000000, -9223372036854775808, 9223372036854775807]:
            check(archive([], integer), [[integer, 0], [0, 0], [0, 0], [0, 0]])
        # A standard GNU long-name extension must preserve base-header clocks.
        raw = extension(b'a' * 150 + b'\0', tarfile.GNUTYPE_LONGNAME) + archive([], -42)
        check(raw, [[-42, 0], [0, 0], [0, 0], [0, 0]])
        for value in ['', '-', '1.', '+1', '1e3', '1.0000000001',
                      '9223372036854775808', '-9223372036854775809', '-9223372036854775808.1']:
            check(archive([('mtime', value)]))
        check(archive([('mtime', '1'), ('mtime', '2')]))
        check(archive(clocks), expired=True)
        check(archive(clocks)[:-512])
        check(archive(clocks) + b'x' + bytes(511))
        bad = bytearray(archive(clocks)); bad[0] ^= 1; check(bad)
        body = b''.join(record(k, v) for k, v in clocks)
        bad = bytearray(archive(clocks)); bad[512 + len(body)] = 1; check(bad)
        check(extension(body) + extension(body) + archive([]))
        check(extension(body, tarfile.XGLTYPE) + archive([]))
        check(archive([('size', '1')]))
        # Record length and termination are checked independently of values.
        check(extension(b'9 mtime=0\n') + archive([]))
        check(extension(record('mtime', '0')[:-1] + b'x') + archive([]))
    print(f'PASS tar clocks: {cases} independent wire cases (signed limits are format checks only)')


if __name__ == '__main__':
    main()
