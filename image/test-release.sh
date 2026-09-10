#!/bin/sh
# SPDX-License-Identifier: BSD-3-Clause
# Destructive only inside a fresh, disposable builder container; never on host.
set -eu
[ -f /run/.containerenv ] || [ -f /.dockerenv ] || { echo 'Disposable container required' >&2; exit 78; }
package=/build/packages/niaos-release_0.1.0_all.deb
original=$(sha256sum /usr/lib/os-release | cut -d ' ' -f 1)
dpkg -i "$package"
test "$(. /etc/os-release; echo "$ID")" = niaos
test "$(sha256sum /usr/lib/os-release.debian | cut -d ' ' -f 1)" = "$original"
dpkg -i "$package"
test "$(. /etc/os-release; echo "$ID")" = niaos
if [ "$#" -eq 1 ]; then
    test "$(dpkg-deb -f "$1" Package)" = base-files
    dpkg -i "$1"
    test "$(. /etc/os-release; echo "$ID")" = niaos
    test "$(sha256sum /usr/lib/os-release.debian | cut -d ' ' -f 1)" = "$original"
    echo 'NIAOS_RELEASE_BASE_FILES_REINSTALL_PASS'
elif [ "$#" -ne 0 ]; then
    echo 'Usage: test-release.sh [same-version-base-files.deb]' >&2
    exit 64
fi
dpkg --remove niaos-release
test "$(sha256sum /usr/lib/os-release | cut -d ' ' -f 1)" = "$original"
test "$(. /etc/os-release; echo "$ID")" = debian
test ! -e /usr/lib/os-release.debian
dpkg --purge niaos-release
test -z "$(dpkg-divert --list /usr/lib/os-release)"
dpkg -i "$package"
dpkg --purge niaos-release
test "$(sha256sum /usr/lib/os-release | cut -d ' ' -f 1)" = "$original"
echo 'NIAOS_RELEASE_INSTALL_REINSTALL_REMOVE_PURGE_PASS'
