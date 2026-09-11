#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Exercise configured publication and source-free accepted metadata recovery."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from compare_root_publication import check


def run(driver, case):
    media = Path(__file__).resolve().parent / 'fixtures/conffiles'
    for name in ('root', 'state', 'store', 'bank', 'source'):
        (case / name).mkdir(mode=0o700)
    (case / 'source/etc').mkdir(mode=0o700)
    source = case / 'source/etc/fixture.conf'
    source.write_bytes(b'local')
    source.chmod(0o600)
    command = [str(driver.resolve()), *(str(case / name) for name in
        ('root', 'state', 'store', 'bank')), str(media)]

    def invoke(arguments, log):
        with log.open('wb') as output:
            result = subprocess.run(command + arguments, stdout=output,
                stderr=subprocess.STDOUT, timeout=600, check=False)
        assert log.stat().st_size <= 1024 * 1024
        print(log.read_text(), end='', flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)

    log = case / 'native.log'
    invoke(['configured-root'], log)
    report = check(case / 'root', case / 'state', case / 'store', case / 'bank', media, log)
    snapshot = (case / 'state/root.state').read_bytes()
    descriptor = (case / 'root/generation.next').read_bytes()
    invoke(['recover', report['accepted_plan']], case / 'recovery.log')
    assert (case / 'state/root.state').read_bytes() == snapshot
    assert (case / 'root/generation.next').read_bytes() == descriptor
    assert source.read_bytes() == b'new'
    report['fresh_process_terminal_recovery'] = True
    (case / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', type=Path, required=True)
    parser.add_argument('--case', type=Path)
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise SystemExit('Run this private fixture as an unprivileged user')
    if args.case:
        args.case.mkdir(mode=0o700, exist_ok=False)
        run(args.driver, args.case.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='nia-configured-publication-') as temporary:
            run(args.driver, Path(temporary))
    print('PASS configured publication and accepted metadata recovery')


if __name__ == '__main__':
    main()
