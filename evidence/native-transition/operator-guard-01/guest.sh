# SPDX-License-Identifier: BSD-3-Clause
set -eu
umask 022
mkdir -m 700 /home/builder/niayan-monitor
cd /home/builder/niayan-monitor
tar -xf /home/builder/runtime.tar
export DEB_BUILD_OPTIONS="parallel=1 nocheck" TZ=UTC
(cd niaos-pkgcore && dpkg-buildpackage -us -uc) > build-component.log 2>&1
export DEB_BUILD_OPTIONS=parallel=1
(cd niaos-root-preparation && dpkg-buildpackage -us -uc) > build-controller.log 2>&1
sudo dpkg -i dependencies/*.deb niaos-pkgcore_*_amd64.deb niaos-root-preparation_0.11.0_amd64.deb > install.log 2>&1
sudo python3 check_operator_guard.py --disposable-vm --report /home/builder/niayan-monitor/result.json
dpkg-query -W gcc gnat gprbuild libgnat-14 libsystemd0 libarchive13t64 libsodium23 python3 > packages.tsv
