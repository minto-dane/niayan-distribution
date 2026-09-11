#!/bin/sh
set -eu
cd /workspace/pkgcore
gprbuild -f -P tests.gpr -j1 run_root_configuration_tests.adb
build/test-bin/run_root_configuration_tests /evidence/case-02/store /evidence/case-02/root /workspace/pkgcore/tests/fixtures/conffiles
