#!/bin/sh
# SPDX-License-Identifier: MIT
# Only the dedicated disposable VM. This rewrites that VM's APT sources.
set -eu
test "$(id -u)" -eq 0
test -f /etc/niaos-image-builder
cd /source
snapshot=$(python3 -c 'import json; print(json.load(open("lock.json"))["snapshot"])')
test "$snapshot" = 20260907T000000Z
rm -f /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list.d/debian.list
cat > /etc/apt/sources.list <<EOF
deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/$snapshot/ trixie main
deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/$snapshot/ trixie-updates main
deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/$snapshot/ trixie-security main
EOF
export DEBIAN_FRONTEND=noninteractive
apt-get update
xargs -r apt-get install -y --no-install-recommends < builder-packages.txt
dpkg-query -W > /build/builder-packages.tsv
