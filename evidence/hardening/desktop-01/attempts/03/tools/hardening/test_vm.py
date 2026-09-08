#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the baseline in a disposable Live VM, including real Japanese input.

The ISO is read-only. Settings affect the guest RAM overlay only. This is runtime
compatibility evidence, not acceptance of a new ISO or persistent boot policy.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
IMAGE = HERE.parent / 'image'
sys.path.insert(0, str(IMAGE))
from vm_console import Guest, firmware_args, install_interrupt_handler


def main():
    install_interrupt_handler()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--iso', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--firmware', choices=('bios', 'uefi', 'secure-boot'), required=True)
    args = ap.parse_args()
    iso = args.iso.resolve(strict=True)
    if not iso.is_file():
        raise ValueError('regular ISO file required')
    args.output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('live_acceptance', IMAGE / 'test-live.py')
    live = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(live)
    payloads = {'audit.py': HERE / 'audit.py', 'baseline.json': HERE / 'baseline.json',
                'nia-hostctl': HERE / 'rootfs/etc/apparmor.d/nia-hostctl',
                '60-niaos-hardening.conf': HERE / 'rootfs/usr/lib/sysctl.d/60-niaos-hardening.conf'}
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in payloads.items()}
    tools = {str(p.relative_to(HERE.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in (Path(__file__), IMAGE / 'vm_console.py', IMAGE / 'test-live.py')}
    with iso.open('rb') as stream:
        iso_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {'result': 'incomplete', 'iso_sha256': iso_hash, 'firmware': args.firmware,
              'payload_sha256': hashes, 'tools_sha256': tools,
              'scope': 'Live RAM-only runtime hardening, KDE IME, user namespaces and Firefox startup',
              'persistent_boot_policy_tested': False, 'native_package_manager_tested': False}
    command = ['qemu-system-x86_64', '-machine', 'q35', '-m', '2048', '-smp', '1',
               '-accel', 'kvm', '-cpu', 'host', '-display', 'none', '-monitor', 'none',
               '-nic', 'user', '-boot', 'd', '-cdrom', str(iso), '-no-reboot']
    command += firmware_args(args.firmware, args.output)
    start = time.monotonic()
    try:
        with Guest(command, args.output, 600) as guest:
            report['argv'] = guest.command
            guest.boot_default_entry()
            guest.expect(b'login:')
            guest.send('niaos\n')
            guest.expect(b':')
            guest.send('live\n')
            guest.expect(b'$')
            source = ('set -eu\ntrap \'printf "\\nNIA_HARDENING_FAIL\\n"\' EXIT\n'
                      'probe=$(mktemp -d /tmp/nia-hardening.XXXXXXXX)\n')
            for name, path in payloads.items():
                encoded = base64.b64encode(path.read_bytes()).decode()
                source += 'base64 -d > "$probe/' + name + '" <<\'NIA_PAYLOAD\'\n' + encoded + '\nNIA_PAYLOAD\n'
            # Observe before changing anything. Refuse to replace an already
            # stricter accepted value with the selected baseline default.
            source += r'''python3 - "$probe" <<'NIA_PREFLIGHT'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1])
policy=json.loads((p/'baseline.json').read_text())
for name,row in policy['sysctl'].items():
    value=int((pathlib.Path('/proc/sys')/name.replace('.','/')).read_text())
    if value in row['accepted'] and value != row['value']:
        raise SystemExit('refusing to weaken an accepted existing value: '+name)
print('All requested sysctls exist; no accepted stricter value will be replaced.')
NIA_PREFLIGHT
sysctl -p "$probe/60-niaos-hardening.conf"
printf '\nNIA_APPARMOR_BEFORE\n'
systemctl status apparmor --no-pager || true
systemctl is-enabled apparmor || true
cat /sys/kernel/security/apparmor/profiles
apparmor_parser -r "$probe/nia-hostctl"
/usr/libexec/nia/hostctl inspect
python3 - <<'NIA_MAC_PROBE'
import ctypes, errno, os, socket, subprocess
library=ctypes.CDLL('libapparmor.so.1', use_errno=True)
library.aa_change_profile.argtypes=[ctypes.c_char_p]
library.aa_change_profile.restype=ctypes.c_int
if library.aa_change_profile(b'nia-hostctl') != 0:
    raise OSError(ctypes.get_errno(), 'cannot enter actual hostctl profile')
with open('/proc/self/attr/current') as f:
    label=f.read().strip()
assert label == 'nia-hostctl (enforce)', label
with open('/proc/sys/kernel/randomize_va_space') as f:
    assert f.read().strip() == '2'
for name,operation in (
    ('secret-read', lambda: os.open('/etc/shadow',os.O_RDONLY)),
    ('file-write', lambda: os.open('/tmp/nia-mac-probe-forbidden',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)),
    ('network', lambda: socket.socket(socket.AF_INET,socket.SOCK_STREAM)),
    ('child-exec', lambda: subprocess.run(['/usr/bin/true'],check=True)),
):
    try:
        operation()
    except OSError as error:
        if error.errno not in (errno.EACCES, errno.EPERM):
            raise
        print('Nia hostctl AppArmor denied '+name)
    else:
        raise RuntimeError('AppArmor allowed forbidden '+name)
print('Nia hostctl AppArmor actual enforcement passed')
NIA_MAC_PROBE
printf '\nNIA_HARDENING_REPORT_BEGIN\n'
python3 "$probe/audit.py" --policy "$probe/baseline.json" --runtime
printf '\nNIA_HARDENING_REPORT_END\n'
test "$(systemctl --failed --no-legend --plain | wc -l)" = 0
systemctl is-active NetworkManager display-manager
timeout 90 sh -c 'until pgrep -u niaos -x plasmashell >/dev/null && ! pgrep -u niaos -x ksplashqml >/dev/null; do sleep 1; done'
trap - EXIT
printf '\nNIA_HARDENING_APPLIED\n'
'''
            guest.script(source, root=True)
            guest.expect(b'NIA_HARDENING_APPLIED', b'NIA_HARDENING_FAIL')
            raw = (args.output / 'serial.log').read_bytes().replace(b'\r', b'')
            match = re.search(rb'\nNIA_HARDENING_REPORT_BEGIN\n(.*?)\nNIA_HARDENING_REPORT_END\n', raw, re.S)
            if not match:
                raise ValueError('missing actual guest hardening report')
            observed = json.loads(match[1])
            if observed['result'] != 'pass' or observed['policy_sha256'] != hashes['baseline.json']:
                raise ValueError('guest report binding or mitigation failure')
            (args.output / 'runtime.json').write_text(json.dumps(observed, indent=2) + '\n')
            report['runtime'] = 'pass'
            live.check_japanese_input(guest)
            report['japanese_input'] = 'pass: KWrite saved 日本語 through Fcitx5/Mozc and KWin Wayland'
            guest.expect(b'$')
            guest.script(r'''set -eu
trap 'printf "\nNIA_HARDENING_USABILITY_FAIL\n"' EXIT
unshare --user --map-root-user true
getent ahostsv4 deb.debian.org
test -S "$XDG_RUNTIME_DIR/wayland-0"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
export WAYLAND_DISPLAY=wayland-0
profile=$(mktemp -d /tmp/nia-firefox.XXXXXXXX)
timeout 90 firefox-esr --headless --no-remote --profile "$profile" --screenshot "$profile/startup.png" about:blank > "$profile/startup.log" 2>&1
test -s "$profile/startup.png"
cat "$profile/startup.log"
trap - EXIT
printf '\nNIA_HARDENING_USABILITY_PASS\n'
''')
            guest.expect(b'NIA_HARDENING_USABILITY_PASS', b'NIA_HARDENING_USABILITY_FAIL')
            report['usability'] = 'pass: unprivileged user namespace, DNS, Firefox headless about:blank screenshot'
            guest.screenshot('desktop.png')
            guest.send('sudo -n systemctl poweroff\n')
            guest.wait_shutdown()
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
