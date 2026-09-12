set -eu
umask 022
mkdir -m 700 /home/builder/niayan-monitor
cd /home/builder/niayan-monitor
tar -xf /home/builder/runtime.tar
export DEB_BUILD_OPTIONS=parallel=1 TZ=UTC
# Reuse the accepted normal-case DEB without rebuilding.
sudo dpkg -i dependencies/*.deb component.deb niaos-root-preparation_0.12.0_amd64.deb > install.log 2>&1
sudo systemctl daemon-reload
sudo systemd-analyze verify niaos-root-bank-check.service niaos-root-session.socket niaos-root-session.service niaos-root-session-seal.service var-lib-niaos-roots.mount
test ! -e /var/lib/niaos/bootstrap.json
test "$(sudo blockdev --getsize64 /dev/vdb)" = 67108864
printf 'label: gpt\n, , L\n' | sudo sfdisk /dev/vdb
sudo udevadm settle
sudo mkfs.ext4 -q /dev/vdb1
sudo python3 - <<'PY'
import json, subprocess
from pathlib import Path
tags=dict(line.split('=',1) for line in subprocess.check_output(['blkid','--probe','--output','export','/dev/vdb1'],text=True).splitlines())
assert tags['TYPE']=='ext4' and tags['PART_ENTRY_SCHEME']=='gpt'
plan=dict(version=1,partition_uuid=tags['PART_ENTRY_UUID'],filesystem_uuid=tags['UUID'],size_bytes=int(subprocess.check_output(['blockdev','--getsize64','/dev/vdb1'])))
path=Path('/etc/niaos/root-bank-device.json');assert not path.exists()
path.write_text(json.dumps(plan)+'\n');path.chmod(0o600)
PY
sudo python3 -I /usr/libexec/niaos/storage_bootstrap.py --initialize > bootstrap.log
sudo python3 check_root_supervisor.py --cancel --disposable-vm --library /home/builder/niayan-monitor/root-handoff.so --report /home/builder/niayan-monitor/result.json
