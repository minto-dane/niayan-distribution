set -eu
umask 022
cd /home/builder/nia-retirement
sudo mkdir -p -m 700 /var/tmp/nia-shared-bank
sudo mount -t tmpfs -o nodev,nosuid,noexec,size=32m,mode=0700 tmpfs /var/tmp/nia-shared-bank
sudo env PYTHONPATH=/usr/libexec/niaos python3 check_root_bank.py --worker /usr/libexec/niaos/root-extract --base /var/tmp/nia-shared-bank --report bank.json
sudo env PYTHONPATH=/usr/libexec/niaos python3 check_root_reinspection.py --worker /usr/libexec/niaos/root-extract --base /var/tmp/nia-shared-bank --report reinspection.json
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
