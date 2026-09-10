#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Install hardening in a fresh VM disk overlay and verify it after Secure Boot.

Accepts only a regular qcow2 fixture from image/test-install.py. The original
disk remains a read-only backing image; no physical disk is accepted.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
IMAGE = HERE.parent / 'image'
sys.path.insert(0, str(IMAGE))
from vm_console import Guest, firmware_args, install_interrupt_handler


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def login(guest):
    guest.expect(b'login:')
    guest.send('niatest\n')
    guest.expect(b':')
    guest.send('niaos-test-only\n')
    guest.expect(b'$')
    guest.send('sudo -v\n')
    guest.expect(b'password for')
    guest.send('niaos-test-only\n')
    guest.expect(b'$')


def main():
    install_interrupt_handler()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base-disk', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    base = args.base_disk.resolve(strict=True)
    if not base.is_file():
        raise ValueError('regular test disk required')
    args.output.mkdir(parents=True, exist_ok=False)
    overlay = (args.output / 'installed.qcow2').resolve()
    before = sha(base)
    subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(base), str(overlay)], check=True)
    payloads = {
        'audit.py': HERE / 'audit.py', 'baseline.json': HERE / 'baseline.json',
        **{p.relative_to(HERE / 'rootfs').as_posix(): p
           for p in sorted((HERE / 'rootfs').rglob('*')) if p.is_file()},
    }
    hashes = {name: sha(path) for name, path in payloads.items()}
    report = {'result': 'incomplete', 'base_disk_sha256_before': before,
              'payload_sha256': hashes, 'tool_sha256': sha(Path(__file__)),
              'vm_console_sha256': sha(IMAGE / 'vm_console.py'),
              'scope': 'prototype files in a disposable overlay; persistent configuration and Secure Boot',
              'native_package_manager_tested': False, 'boots': []}
    start = time.monotonic()
    try:
        for phase in ('install', 'verify-reboot'):
            output = args.output / phase
            output.mkdir()
            command = ['qemu-system-x86_64', '-machine', 'q35', '-m', '2048', '-smp', '1',
                       '-accel', 'kvm', '-cpu', 'host', '-display', 'none', '-monitor', 'none',
                       '-nic', 'none', '-no-reboot', '-boot', 'c', '-drive',
                       f'file={overlay},format=qcow2,if=virtio']
            command += firmware_args('secure-boot', output)
            row = {'phase': phase, 'result': 'incomplete'}
            report['boots'].append(row)
            with Guest(command, output, 600) as guest:
                row['argv'] = guest.command
                login(guest)
                source = 'set -eu\ntrap \'printf "\\nNIA_PERSISTENT_FAIL\\n"\' EXIT\n'
                source += 'test "$(od -An -j4 -N1 -t u1 /sys/firmware/efi/efivars/SecureBoot-* | tr -d \' \')" = 1\n'
                if phase == 'install':
                    # The auditor stays in a private fixture directory. Product
                    # files go to standard paths only inside this new disk.
                    source += 'install -d -m 0700 /root/nia-hardening-test\n'
                    for name, path in payloads.items():
                        dest = '/root/nia-hardening-test/' + name if '/' not in name else '/' + name
                        source += 'install -d -m 0755 ' + str(Path(dest).parent) + '\n' if '/' in name else ''
                        source += 'base64 -d > ' + dest + " <<'NIA_PAYLOAD'\n" + base64.b64encode(path.read_bytes()).decode() + '\nNIA_PAYLOAD\n'
                        source += 'chmod 0644 ' + dest + '\n'
                    # Check for a potential security downgrade before reboot.
                    source += r'''python3 - <<'NIA_PREFLIGHT'
import json, pathlib
p=json.loads(pathlib.Path('/root/nia-hardening-test/baseline.json').read_text())
for name,row in p['sysctl'].items():
    value=int((pathlib.Path('/proc/sys')/name.replace('.','/')).read_text())
    if value in row['accepted'] and value != row['value']:
        raise SystemExit('refusing to weaken existing sysctl '+name)
NIA_PREFLIGHT
systemd-analyze verify /usr/lib/systemd/system/niaos-hostctl-confinement.service
systemctl daemon-reload
systemctl enable niaos-hostctl-confinement.service
'''
                else:
                    source += 'systemctl is-enabled niaos-hostctl-confinement.service\n'
                    source += 'systemctl is-active niaos-hostctl-confinement.service\n'
                    source += 'systemctl is-active NetworkManager display-manager\n'
                    source += 'test "$(systemctl --failed --no-legend --plain | wc -l)" = 0\n'
                    source += '/usr/libexec/nia/hostctl inspect\n'
                    for name, digest in hashes.items():
                        dest = '/root/nia-hardening-test/' + name if '/' not in name else '/' + name
                        source += "printf '%s  %s\\n' " + digest + ' ' + dest + ' | sha256sum -c -\n'
                    source += r'''printf '\nNIA_PERSISTENT_REPORT_BEGIN\n'
python3 /root/nia-hardening-test/audit.py --policy /root/nia-hardening-test/baseline.json --runtime
printf '\nNIA_PERSISTENT_REPORT_END\n'
'''
                source += 'trap - EXIT\nprintf "\\nNIA_PERSISTENT_PASS\\n"\n'
                guest.script(source, root=True)
                guest.expect(b'NIA_PERSISTENT_PASS', b'NIA_PERSISTENT_FAIL')
                if phase == 'verify-reboot':
                    raw = (output / 'serial.log').read_bytes().replace(b'\r', b'')
                    match = re.search(rb'\nNIA_PERSISTENT_REPORT_BEGIN\n(.*?)\nNIA_PERSISTENT_REPORT_END\n', raw, re.S)
                    if not match:
                        raise ValueError('missing boot-time mitigation observation')
                    observed = json.loads(match[1])
                    if observed['result'] != 'pass' or observed['policy_sha256'] != hashes['baseline.json']:
                        raise ValueError('reboot mitigation failure or binding mismatch')
                    (args.output / 'runtime.json').write_text(json.dumps(observed, indent=2) + '\n')
                guest.send('sudo -n systemctl poweroff\n')
                guest.wait_shutdown()
                row['result'] = 'pass'
        if sha(base) != before:
            raise ValueError('original test disk changed')
        report['base_disk_sha256_after'] = before
        report['result'] = 'pass'
    except BaseException as error:
        report['result'] = 'fail'
        report['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - start, 3)
        (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
