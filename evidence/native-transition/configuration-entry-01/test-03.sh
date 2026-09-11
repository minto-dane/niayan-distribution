#!/bin/sh
set -eu
cd /workspace/pkgcore
gprbuild -f -P tests.gpr -j1 run_conffile_observation_tests.adb run_tar_output_tests.adb run_deb_payload_tests.adb
build/test-bin/run_conffile_observation_tests /evidence/case-03/store /evidence/case-03/root tests/fixtures/root-archive
build/test-bin/run_tar_output_tests /evidence/tar-01/store /evidence/tar-01/export
