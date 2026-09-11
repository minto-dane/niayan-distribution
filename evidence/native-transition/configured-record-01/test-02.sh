#!/bin/sh
set -eu
cd /workspace/pkgcore
gprbuild -f -P tests.gpr -j1 run_root_configuration_tests.adb
build/test-bin/run_root_configuration_tests /evidence/case-01/store /evidence/case-01/root /workspace/pkgcore/tests/fixtures/conffiles
