#!/bin/sh
set -eu
cd /workspace/pkgcore
gprbuild -f -P tests.gpr -j1 run_conffile_observation_tests.adb run_deb_payload_tests.adb
build/test-bin/run_conffile_observation_tests /evidence/case-04/store /evidence/case-04/root /workspace/pkgcore/tests/fixtures/root-archive
build/test-bin/run_deb_payload_tests /evidence/payload-04/store /workspace/pkgcore/tests/fixtures/deb-payload
make -C /workspace/worker BUILD=/workspace/build all
