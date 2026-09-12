#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Run the KDE image acceptance matrix sequentially inside a bounded builder."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from vm_console import install_interrupt_handler, tool_hashes, retire_install_disks

HERE = Path(__file__).resolve().parent


def main():
    install_interrupt_handler()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iso', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--retain-disks', action='store_true',
                        help='keep successful installation disks for an explicit follow-up; failures always retain them')
    args = parser.parse_args()
    iso = args.iso.resolve(strict=True)
    if not iso.is_file():
        raise ValueError('ISO must be a regular file')
    output = args.output.resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    tests = [
        ('live-bios', 'test-live.py', ['--iso', str(iso), '--firmware', 'bios', '--input-check']),
        ('live-uefi-network', 'test-live.py', ['--iso', str(iso), '--firmware', 'uefi', '--network-check']),
        ('live-secure-boot', 'test-live.py', ['--iso', str(iso), '--firmware', 'secure-boot']),
        ('install-uefi-offline', 'test-install.py', ['--iso', str(iso), '--firmware', 'uefi']),
        ('install-bios-network', 'test-install.py', ['--iso', str(iso), '--firmware', 'bios', '--network']),
        ('installed-secure-boot', 'test-live.py',
         ['--disk', str(output / 'install-uefi-offline/installed.qcow2'),
          '--firmware', 'secure-boot', '--mirror-policy', 'media']),
    ]
    report = {'result': 'incomplete', 'desktop': 'kde', 'test_tools_sha256': tool_hashes(),
              'tests': [], 'production_qualified': False, 'disk_cleanup': [],
              'disk_retention': 'explicit' if args.retain_disks else 'until-suite-success',
              'scope': 'QEMU BIOS/UEFI/Secure Boot, Japanese input, offline/online installation and APT metadata'}
    with iso.open('rb') as stream:
        report['iso_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    start = time.monotonic()

    def save():
        report['elapsed_seconds'] = round(time.monotonic() - start, 3)
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    save()
    try:
        for name, script, options in tests:
            print('Running ' + name, flush=True)
            command = [sys.executable, str(HERE / script), *options, '--output', str(output / name)]
            row = {'name': name, 'result': 'incomplete', 'report': name + '/report.json'}
            report['tests'].append(row)
            save()
            with (output / (name + '.log')).open('wb') as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
            child = json.loads((output / name / 'report.json').read_text())
            if child['result'] != 'pass':
                raise ValueError('child did not report acceptance: ' + name)
            row['result'] = 'pass'
            save()
        # installed-secure-boot still needs the UEFI disk; retire only after the
        # complete matrix and its QEMU processes have finished successfully.
        if not args.retain_disks:
            retire_install_disks(output, report['disk_cleanup'])
        report['result'] = 'pass'
    except BaseException as error:
        report['result'] = 'fail'
        if report['tests'] and report['tests'][-1]['result'] == 'incomplete':
            report['tests'][-1]['result'] = 'fail'
        report['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
