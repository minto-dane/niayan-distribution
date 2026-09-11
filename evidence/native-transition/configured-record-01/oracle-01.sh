#!/bin/sh
set -eu
cd /workspace/pkgcore
python3 -B tests/check_configured_root.py --native /evidence/test-02.log --cas /evidence/case-01/store --output /evidence/root-oracle-01
python3 -B tests/check_configured_root_record.py --native /evidence/test-02.log --cas /evidence/case-01/store --driver /workspace/pkgcore/build/test-bin/run_root_configuration_tests --output /evidence/record-oracle-01
