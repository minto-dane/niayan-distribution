#!/bin/sh
set -eu
cd /workspace/pkgcore
for name in local backup vendor override; do
 mkdir -m 700 /evidence/export-04/"$name"-store
 build/test-bin/run_deb_payload_tests /evidence/export-04/"$name"-store /evidence/export-04 "$name".deb > /evidence/export-04/"$name".native.log
 done
python3 -B tests/check_configuration_entry.py --native /evidence/test-04.log --cas /evidence/case-04/store --output /evidence/export-04 --native-roundtrip
python3 -B tests/check_tar_output.py /evidence/tar-01/export
