#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Boot actual media with QEMU; optional outbound APT metadata acceptance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from vm_console import Guest, firmware_args, install_interrupt_handler, tool_hashes

PROBE = r'''set -eu
trap 'printf "\nNIAOS_LIVE_PROBE_FAIL\n"' EXIT
cat /etc/os-release
. /etc/os-release
test "$ID" = niaos
test "$VERSION_CODENAME" = trixie
test "$(cat /proc/1/comm)" = systemd
audit=$(dpkg --audit)
test -z "$audit"
systemctl --failed --no-pager
dpkg-query -W niaos-release niaos-base niaos-assurance niaos-pkgcore niaos-statecore niaos-controlcore niaos-configcore niaos-resolvercore niaos-capsulecore
systemctl is-active NetworkManager
case "$NIA_DESKTOP" in
  kde)
    dpkg-query -W niaos-desktop-kde
    systemctl is-active display-manager
    if [ "$NIA_RUNTIME" = live ]; then timeout 90 sh -c 'until pgrep -u niaos -x plasmashell >/dev/null && ! pgrep -u niaos -x ksplashqml >/dev/null; do sleep 1; done'; fi
    ;;
  gnome)
    dpkg-query -W niaos-desktop-gnome
    systemctl is-active display-manager
    if [ "$NIA_RUNTIME" = live ]; then timeout 90 sh -c 'until pgrep -u niaos -x gnome-shell >/dev/null; do sleep 1; done'; fi
    ;;
  server) ;;
esac
test -x /usr/bin/nia
test -x /usr/libexec/nia/hostctl
/usr/libexec/nia/hostctl inspect
printf '\nNIAOS_APT_CONFIGURATION\n'
cat /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources 2>/dev/null || true
find /etc/ssh -name 'ssh_host_*_key' -type f 2>/dev/null || true
test -z "$(find /etc/ssh -name 'ssh_host_*_key' -type f 2>/dev/null)"
if apt-config dump | grep -i 'Check-Valid-Until.*false'; then exit 1; fi
if grep -R 'snapshot.debian.org' /etc/apt/sources.list /etc/apt/sources.list.d; then exit 1; fi
sources=$(cat /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources 2>/dev/null | sed '/^[[:space:]]*#/d')
if [ "$NIA_MIRROR_POLICY" = media ]; then
  printf '%s\n' "$sources" | grep '^deb cdrom:'
  if printf '%s\n' "$sources" | grep -E 'https?://'; then exit 1; fi
else
  protocol=https
  if [ "$NIA_RUNTIME" = installed ]; then protocol='https?'; fi
  printf '%s\n' "$sources" | grep -E "${protocol}://deb.debian.org/debian"
  printf '%s\n' "$sources" | grep -E "${protocol}://security.debian.org/debian-security"
  printf '%s\n' "$sources" | grep trixie-updates
  printf '%s\n' "$sources" | grep trixie-security
fi
apt-config dump | grep 'origin=Debian,codename=trixie-security,label=Debian-Security'
if [ "$NIA_RUNTIME" = installed ]; then
  test ! -d /run/live/medium
  test -z "$(getent passwd niaos)"
fi
case "$NIA_BOOT_MODE" in
  bios) test ! -d /sys/firmware/efi ;;
  uefi) test -d /sys/firmware/efi ;;
  secure-boot)
    test -d /sys/firmware/efi
    test "$(od -An -j4 -N1 -t u1 /sys/firmware/efi/efivars/SecureBoot-* | tr -d ' ')" = 1
    ;;
esac
if [ "$NIA_NETWORK_CHECK" = yes ]; then
  timeout 90 sh -c 'until ip -4 route show default | grep -q default; do sleep 1; done'
  timeout 240 apt-get -o APT::Update::Error-Mode=any -o Acquire::Retries=1 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update
fi
trap - EXIT
printf '\nNIAOS_LIVE_PROBE_PASS\n'
'''


def check_japanese_input(guest):
    def run(script, marker):
        content = ('set -eu\ntrap \'printf "\\nNIAOS_IME_FAIL\\n"\' EXIT\n'
                   'export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"\n'
                   'export WAYLAND_DISPLAY=wayland-0\n'
                   + script + '\ntrap - EXIT\nprintf "\\n' + marker + '\\n"\n')
        guest.expect(b'$')
        guest.script(content)
        guest.expect(marker.encode(), b'NIAOS_IME_FAIL')

    run('test -S "$XDG_RUNTIME_DIR/wayland-0"\n'
        'timeout 90 sh -c \'until busctl --user --no-pager list | grep -q org.fcitx.Fcitx5; do sleep 1; done\'\n'
        'pgrep -a -u "$(id -u)" fcitx5\n'
        'WAYLAND_DISPLAY=wayland-0 kwrite "$HOME/niaos-ime-test.txt" '
        '>/tmp/niaos-ime-editor.log 2>&1 &', 'NIAOS_EDITOR_STARTED')
    time.sleep(5)
    guest.screenshot('input-editor.png')
    guest.key('ctrl', 'a')
    run('fcitx5-remote -s mozc\nfcitx5-remote -o\n'
        'fcitx5-remote -n\n'
        'test "$(fcitx5-remote -n)" = mozc', 'NIAOS_IME_ACTIVE')
    for letter in 'nihongo':
        guest.key(letter)
    guest.key('spc')
    guest.key('ret')
    guest.key('ctrl', 's')
    time.sleep(1)
    run('cat "$HOME/niaos-ime-test.txt"\n'
        'test "$(cat "$HOME/niaos-ime-test.txt")" = "日本語"', 'NIAOS_IME_PASS')
    guest.screenshot('japanese-input.png')


def main():
    install_interrupt_handler()
    ap = argparse.ArgumentParser(description=__doc__)
    media = ap.add_mutually_exclusive_group(required=True)
    media.add_argument('--iso', type=Path)
    media.add_argument('--disk', type=Path, help='disk created by test-install.py only')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--firmware', choices=('bios', 'uefi', 'secure-boot'), required=True)
    ap.add_argument('--desktop', choices=('kde', 'gnome', 'server'), default='kde')
    ap.add_argument('--timeout', type=int, default=600)
    ap.add_argument('--network-check', action='store_true',
                    help='enable QEMU user networking and authenticate current APT metadata')
    ap.add_argument('--input-check', action='store_true',
                    help='type and save Japanese text through the live KDE Wayland desktop')
    ap.add_argument('--mirror-policy', choices=('debian', 'media'), default='debian',
                    help='media only for the explicit offline/no-mirror installer fixture')
    args = ap.parse_args()
    if args.input_check and (not args.iso or args.desktop != 'kde'):
        ap.error('--input-check requires a live KDE ISO')
    if args.mirror_policy == 'media' and (not args.disk or args.network_check):
        ap.error('media policy requires an installed disk without a network check')
    args.output.mkdir(parents=True, exist_ok=False)
    path = (args.iso or args.disk).resolve(strict=True)
    if not path.is_file():
        raise ValueError('test media must be a regular file, never a host block device')
    mode = 'live' if args.iso else 'installed'
    command = ['qemu-system-x86_64', '-machine', 'q35', '-m', '2048', '-smp', '1',
               '-accel', 'kvm' if os.access('/dev/kvm', os.R_OK | os.W_OK) else 'tcg',
               '-display', 'none', '-monitor', 'none', '-nic',
               'user' if args.network_check else 'none', '-no-reboot']
    if args.iso:
        command += ['-boot', 'd', '-cdrom', str(path)]
    else:
        command += ['-boot', 'c', '-drive', f'file={path},format=qcow2,if=virtio']
    command += firmware_args(args.firmware, args.output)
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {'result': 'incomplete', 'mode': mode, 'firmware': args.firmware,
              'desktop': args.desktop, 'media_sha256_before': digest,
              'network': 'outbound-user-mode' if args.network_check else 'none',
              'test_tools_sha256': tool_hashes(),
              'japanese_input_requested': args.input_check,
              'mirror_policy': args.mirror_policy,
              'production_qualified': False}
    start = time.monotonic()
    try:
        with Guest(command, args.output, args.timeout) as guest:
            report['argv'] = guest.command
            if args.iso:
                guest.boot_default_entry()
            guest.expect(b'login:')
            guest.send('niaos\n' if mode == 'live' else 'niatest\n')
            # PAM uses the selected locale (e.g. Japanese パスワード:).
            guest.expect(b':')
            guest.send('live\n' if mode == 'live' else 'niaos-test-only\n')
            guest.expect(b'$')
            prefix = ('NIA_BOOT_MODE=' + args.firmware + '\nNIA_DESKTOP=' + args.desktop
                      + '\nNIA_RUNTIME=' + mode + '\nNIA_NETWORK_CHECK='
                      + ('yes' if args.network_check else 'no')
                      + '\nNIA_MIRROR_POLICY=' + args.mirror_policy + '\n')
            # Echoed input cannot contain the unencoded acceptance marker.
            if mode == 'installed':
                guest.send('sudo -v\n')
                guest.expect(b'password for')
                guest.send('niaos-test-only\n')
                guest.expect(b'$')
            guest.script(prefix + PROBE, root=True)
            guest.expect(b'NIAOS_LIVE_PROBE_PASS', b'NIAOS_LIVE_PROBE_FAIL')
            guest.screenshot()
            if args.input_check:
                check_japanese_input(guest)
                report['japanese_input'] = 'passed: KWrite, KWin Wayland, Fcitx5/Mozc, 日本語'
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
