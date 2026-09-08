#!/bin/sh
# SPDX-License-Identifier: MIT
# Prepared /build only, inside the pinned container with private mount namespace.
set -eu
[ "$(id -u)" -eq 0 ] || { echo 'live-build requires root inside its builder' >&2; exit 78; }
[ -f /run/.containerenv ] || [ -f /.dockerenv ] || [ -f /etc/niaos-image-builder ] || { echo 'Disposable container or dedicated VM builder required' >&2; exit 78; }
cd /build/live
. ./nia-image.env
export SOURCE_DATE_EPOCH TZ=UTC
test -f config/packages.chroot/niaos-release_0.1.0_all.deb
# Fail before bootstrap in user namespaces that cannot create device nodes on
# this filesystem. A regular file at /dev/null can make APT wait indefinitely.
probe=$(mktemp -d .nia-device-check.XXXXXXXX)
trap 'rm -f "$probe/null"; rmdir "$probe"' EXIT
if ! mknod "$probe/null" c 1 3; then
    echo 'This filesystem cannot host chroot devices; use a dedicated builder VM.' >&2
    exit 78
fi
test -c "$probe/null"
printf '%s' test > "$probe/null"
rm "$probe/null"
rmdir "$probe"
trap - EXIT
python3 /source/prepare-installer.py
lb config
case "${1:-}" in
    --clean) lb clean ;;
    '') ;;
    *) echo 'Usage: build-live.sh [--clean]' >&2; exit 64 ;;
esac
lb build
