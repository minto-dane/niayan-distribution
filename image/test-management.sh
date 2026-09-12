#!/bin/sh
# SPDX-License-Identifier: BSD-3-Clause
# Package acceptance in a fresh disposable container only.
set -eu
[ "${NIAYAN_DISPOSABLE_PACKAGE_TEST:-}" = 1 ] || exit 78
[ -f /run/.containerenv ] || [ -f /.dockerenv ] || exit 78
[ "$(id -u)" -eq 0 ] || exit 78
package=${1:?Usage: test-management.sh /path/to/niayan-management.deb}
test "$(dpkg-deb -f "$package" Package)" = niayan-management
dpkg -i "$package"
for command in installp lslpp lppchk install_all_updates instfix inutoc geninstall suma lppmgr epkg emgr emgr_download_ifix
do
    test -L "/usr/bin/$command"
    "$command" --help > /dev/null
done
test ! -e /usr/bin/nia
test ! -e /usr/bin/niactl
# Exercise the installed module closure, translated presentation and actual
# media indexing under an ordinary account, with no native controller running.
runuser -u nobody -- /usr/bin/python3 -I - <<'CHECK'
import os, pathlib, subprocess, tempfile
with tempfile.TemporaryDirectory(prefix='niayan-management-') as name:
    root=pathlib.Path(name)
    control=root/'payload/DEBIAN/control';control.parent.mkdir(parents=True)
    control.write_text('Package: niayan-media-fixture\nVersion: 1.0\nArchitecture: all\nMaintainer: Fixture <fixture@example.invalid>\nDescription: local package acceptance fixture\n')
    subprocess.run(['dpkg-deb','--build',str(root/'payload'),str(root/'fixture.deb')],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['inutoc',str(root)],check=True)
    listing=subprocess.check_output(['installp','-L','-d',str(root)],text=True)
    assert 'niayan-media-fixture' in listing
    english=subprocess.check_output(['epkg','--help'],env={**os.environ,'LC_ALL':'C'},text=True)
    japanese=subprocess.check_output(['epkg','--help'],env={**os.environ,'LC_ALL':'ja_JP.UTF-8'},text=True)
    assert english != japanese and 'niayan' in english
    result=subprocess.run(['installp','-a','-d',str(root),'niayan-media-fixture'],capture_output=True,text=True)
    assert result.returncode == 1 and 'not connected' in result.stderr
CHECK
dpkg --purge niayan-management
test ! -e /usr/bin/installp
test ! -d /usr/lib/niayan/management
printf '%s\n' NIAYAN_MANAGEMENT_PACKAGE_PASS
