#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Install the built ISO to a newly created, isolated QEMU disk and boot it."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from vm_console import Guest, firmware_args, install_interrupt_handler, tool_hashes

HERE = Path(__file__).resolve().parent


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    install_interrupt_handler()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--iso', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--firmware', choices=('bios', 'uefi'), default='uefi')
    ap.add_argument('--desktop', choices=('kde', 'gnome', 'server'), default='kde')
    ap.add_argument('--timeout', type=int, default=1200)
    ap.add_argument('--network', action='store_true', help='also configure a Debian mirror and verify APT after reboot')
    args = ap.parse_args()
    iso = args.iso.resolve(strict=True)
    if not iso.is_file():
        raise ValueError('ISO must be a regular file')
    output = args.output.resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    disk = output / 'installed.qcow2'
    subprocess.run(['qemu-img', 'create', '-f', 'qcow2', str(disk), '32G'], check=True)
    with (output / 'extraction.log').open('wb') as log:
        subprocess.run(['xorriso', '-osirrox', 'on', '-indev', str(iso),
                        '-extract', '/install/vmlinuz', str(output / 'vmlinuz'),
                        '-extract', '/install/initrd.gz', str(output / 'original-initrd.gz')],
                       check=True, stdout=log, stderr=log)
    # Keep live-build's existing preseed directives, then add VM-only answers.
    archive = output / 'original.cpio'
    size = 0
    with gzip.open(output / 'original-initrd.gz', 'rb') as source, archive.open('wb') as target:
        while block := source.read(1024**2):
            size += len(block)
            if size > 1024**3:
                raise ValueError('installer initrd exceeds the test input budget')
            target.write(block)
    with archive.open('rb') as source:
        original = subprocess.run(['cpio', '-i', '--to-stdout', 'preseed.cfg', './preseed.cfg'],
                                  stdin=source, capture_output=True, check=True).stdout
    seed = output / 'seed'
    seed.mkdir()
    preseed = original + b'\n' + (HERE / 'fixtures/install-vm.cfg').read_bytes()
    if args.network:
        preseed += b'\n' + (HERE / 'fixtures/install-network.cfg').read_bytes()
    (seed / 'preseed.cfg').write_bytes(preseed)
    (seed / 'nia-test-grub.cfg').write_text('GRUB_CMDLINE_LINUX="console=tty0 console=ttyS0,115200n8"\n')
    overlay = subprocess.run(['cpio', '-o', '-H', 'newc', '--owner=0:0'], cwd=seed,
                             input=b'preseed.cfg\nnia-test-grub.cfg\n',
                             capture_output=True, check=True).stdout
    shutil.copyfile(output / 'original-initrd.gz', output / 'test-initrd.gz')
    with (output / 'test-initrd.gz').open('ab') as target:
        target.write(gzip.compress(overlay, mtime=0))
    archive.unlink()
    command = ['qemu-system-x86_64', '-machine', 'q35', '-m', '2048', '-smp', '1',
               '-accel', 'kvm' if os.access('/dev/kvm', os.R_OK | os.W_OK) else 'tcg',
               '-display', 'none', '-monitor', 'none', '-nic',
               'user' if args.network else 'none', '-no-reboot',
               '-drive', f'file={disk},format=qcow2,if=none,id=target',
               '-device', 'virtio-blk-pci,drive=target,serial=NIAOS_TEST_DISK',
               '-cdrom', str(iso), '-kernel', str(output / 'vmlinuz'),
               '-initrd', str(output / 'test-initrd.gz'), '-append',
               'auto=true priority=critical preseed/file=/preseed.cfg '
               'DEBIAN_FRONTEND=text fb=false console=ttyS0,115200n8']
    command += firmware_args(args.firmware, output)
    report = {'result': 'incomplete', 'iso_sha256': digest(iso),
              'installer_kernel_sha256': digest(output / 'vmlinuz'),
              'original_initrd_sha256': digest(output / 'original-initrd.gz'),
              'test_initrd_sha256': digest(output / 'test-initrd.gz'),
              'firmware': args.firmware, 'desktop': args.desktop,
              'test_tools_sha256': tool_hashes(),
              'scope': 'VM-only preseed, new virtual disk, installation and reboot',
              'network_and_mirror_enabled': args.network,
              'production_qualified': False}
    start = time.monotonic()
    try:
        with Guest(command, output, args.timeout) as guest:
            report['argv'] = guest.command
            guest.expect(b'NIAOS_INSTALL_FINISHED')
            # late_command runs before the remaining finish-install steps.
            # Those steps include cleanup and service configuration, not just
            # the poweroff operation exercised by the Live test.
            guest.wait_shutdown(timeout=300)
        reboot = output / 'reboot'
        reboot_command = ['python3', str(HERE / 'test-live.py'), '--disk', str(disk),
                          '--output', str(reboot), '--firmware', args.firmware,
                          '--desktop', args.desktop, '--timeout', '600']
        reboot_command += ['--network-check'] if args.network else ['--mirror-policy', 'media']
        subprocess.run(reboot_command, check=True)
        report['result'] = 'pass'
        report['reboot'] = json.loads((reboot / 'report.json').read_text())
    except BaseException as error:
        report['result'] = 'fail'
        report['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - start, 3)
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
