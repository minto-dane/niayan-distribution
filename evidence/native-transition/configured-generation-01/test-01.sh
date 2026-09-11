#!/bin/sh
set -eu
cd /workspace/pkgcore
gprbuild -f -P tests.gpr -j1 run_root_configuration_tests.adb run_root_archive_tests.adb run_generation_stage_tests.adb run_generation_publication_tests.adb
build/test-bin/run_root_configuration_tests /evidence/root-01/store /evidence/root-01/root /workspace/pkgcore/tests/fixtures/conffiles > /evidence/root-test-01.log 2>&1
cat /evidence/root-test-01.log
python3 -B tests/check_configured_root_current.py --native /evidence/root-test-01.log --cas /evidence/root-01/store --root /evidence/root-01/root --driver /workspace/pkgcore/build/test-bin/run_root_configuration_tests --output /evidence/current-oracle-01
python3 -B tests/check_configured_root.py --native /evidence/root-test-01.log --cas /evidence/root-01/store --output /evidence/root-oracle-01
build/test-bin/run_root_archive_tests /evidence/archive-01/store /workspace/pkgcore/tests/fixtures/root-archive > /evidence/archive-test-01.log 2>&1
cat /evidence/archive-test-01.log
build/test-bin/run_generation_stage_tests /evidence/stage-01/root /evidence/stage-01/state /evidence/stage-01/store > /evidence/stage-test-01.log 2>&1
cat /evidence/stage-test-01.log
