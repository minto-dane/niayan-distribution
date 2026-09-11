#!/bin/sh
set -eu
cd /workspace/pkgcore
python3 -B tests/make_conffile_fixtures.py --check
python3 -B tests/check_configured_root.py --native /evidence/test-02.log --cas /evidence/case-02/store --output /evidence/export-ci
