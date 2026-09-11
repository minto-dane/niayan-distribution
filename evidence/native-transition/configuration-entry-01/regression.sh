#!/bin/sh
set -eu
cd /workspace/pkgcore
gprbuild -f -P tests.gpr -j1 run_root_archive_tests.adb run_root_configuration_tests.adb
build/test-bin/run_root_archive_tests /evidence/root-regression/store /workspace/pkgcore/tests/fixtures/root-archive > /evidence/root-regression/native.log
build/test-bin/run_root_configuration_tests /evidence/configuration-regression/store /evidence/configuration-regression/root /workspace/pkgcore/tests/fixtures/conffiles > /evidence/configuration-regression/native.log
python3 -B tests/check_configuration_entry.py --native /evidence/test-04.log --cas /evidence/case-04/store --output /evidence/export-ci --driver /workspace/pkgcore/build/test-bin/run_deb_payload_tests
