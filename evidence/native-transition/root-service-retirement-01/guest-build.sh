set -eu
umask 022
mkdir -m 700 /home/builder/nia-retirement
cd /home/builder/nia-retirement
tar -xf /home/builder/nia-retirement.tar
export DEB_BUILD_OPTIONS=parallel=1 TZ=UTC
mkdir build-a build-b
cp -a source build-a/source
cp -a source build-b/source
(cd build-a/source && dpkg-buildpackage -us -uc) > build-a.log 2>&1
(cd build-b/source && dpkg-buildpackage -us -uc) > build-b.log 2>&1
cmp build-a/niaos-root-preparation_0.8.0_amd64.deb build-b/niaos-root-preparation_0.8.0_amd64.deb
cmp build-a/niaos-root-preparation-dbgsym_0.8.0_amd64.deb build-b/niaos-root-preparation-dbgsym_0.8.0_amd64.deb
cmp build-a/niaos-root-preparation_0.8.0.dsc build-b/niaos-root-preparation_0.8.0.dsc
cmp build-a/niaos-root-preparation_0.8.0.tar.xz build-b/niaos-root-preparation_0.8.0.tar.xz
sha256sum build-a/*.deb build-a/*.dsc build-a/*.tar.xz > package-sha256.txt
sudo dpkg -i dependencies/*.deb component.deb old.deb > install-old.log 2>&1
sudo python3 check_root_service_upgrade.py --disposable-vm --old old.deb --new build-a/niaos-root-preparation_0.8.0_amd64.deb --mode live --report upgrade-live-old.json
sudo python3 check_root_service_upgrade.py --disposable-vm --old old.deb --new build-a/niaos-root-preparation_0.8.0_amd64.deb --mode offline --report upgrade-offline.json
# This fresh fixture has no native storage. Remove its inactive old package,
# then exercise a fully configured initial installation of the replacement.
test ! -e /var/lib/niaos/bootstrap.json
sudo dpkg --purge niaos-root-preparation > purge-old.log 2>&1
sudo dpkg -i build-a/niaos-root-preparation_0.8.0_amd64.deb > install.log 2>&1
sudo systemctl daemon-reload
sudo systemd-analyze verify niaos-root-bank-check.service niaos-root-session.socket niaos-root-session.service niaos-root-session-seal.service var-lib-niaos-roots.mount
if systemctl is-active --quiet niaos-root-session.socket; then exit 1; fi
if systemctl is-enabled --quiet niaos-root-session.socket; then exit 1; fi
sudo mkdir -m 700 /var/tmp/nia-shared-bank
sudo mount -t tmpfs -o nodev,nosuid,noexec,size=32m,mode=0700 tmpfs /var/tmp/nia-shared-bank
sudo python3 check_root_bank.py --worker /usr/libexec/niaos/root-extract --base /var/tmp/nia-shared-bank --report bank.json
sudo python3 check_root_reinspection.py --worker /usr/libexec/niaos/root-extract --base /var/tmp/nia-shared-bank --report reinspection.json
sudo umount /var/tmp/nia-shared-bank
# Only the private 64 MiB disk created for this VM is formatted.
test "$(sudo blockdev --getsize64 /dev/vdb)" = 67108864
printf 'label: gpt\n, , L\n' | sudo sfdisk /dev/vdb
sudo udevadm settle
sudo mkfs.ext4 -q /dev/vdb1
sudo python3 check_bank_device.py --device /dev/vdb1 --report /home/builder/nia-retirement/bootstrap.json
sudo systemctl start niaos-root-session.socket niaos-root-session.service
sudo python3 check_root_service_upgrade.py --disposable-vm --old old.deb --new build-a/niaos-root-preparation_0.8.0_amd64.deb --mode live --report upgrade-live-active.json
sudo systemctl stop niaos-root-session.socket niaos-root-session.service
