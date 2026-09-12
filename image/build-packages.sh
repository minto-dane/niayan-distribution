#!/bin/sh
# SPDX-License-Identifier: BSD-3-Clause
# Run unprivileged in the pinned builder, with the prepared directory at /build.
set -eu
[ "$(id -u)" -ne 0 ] || { echo 'Build packages as an ordinary user' >&2; exit 78; }
export DEB_BUILD_OPTIONS=parallel=1 TZ=UTC
. /build/live/nia-image.env
export SOURCE_DATE_EPOCH
for package in niaos-integration niayan-management niaos-assurance niaos-pkgcore niaos-statecore \
               niaos-controlcore niaos-configcore niaos-resolvercore niaos-capsulecore
do
    (cd "/build/packages/$package"; dpkg-buildpackage -us -uc)
done
mkdir -p /build/live/config/packages.chroot
desktop=$(head -n 1 /build/live/config/package-lists/niaos.list.chroot)
for package in /build/packages/*.deb
do
    case "$package" in
        *-dbgsym_*) continue;;
        */niaos-desktop-*)
            case "$(basename "$package")" in "$desktop"_*) ;; *) continue;; esac
            ;;
    esac
    cp "$package" /build/live/config/packages.chroot/
done
