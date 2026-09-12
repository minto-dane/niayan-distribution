# SPDX-License-Identifier: BSD-3-Clause
set -eu
cd /home/builder/niayan-monitor
sudo journalctl -b -1 -u polkit.service --no-pager -n 80 || true
sudo python3 check_operator_guard.py --disposable-vm --report /home/builder/niayan-monitor/result.json
dpkg-query -W gcc gnat gprbuild libgnat-14 libsystemd0 libarchive13t64 libsodium23 python3 > packages.tsv
