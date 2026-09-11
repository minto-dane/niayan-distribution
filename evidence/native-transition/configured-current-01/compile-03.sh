#!/bin/sh
set -eu
cd /workspace/pkgcore
gprbuild -f -P tests.gpr -j1 run_root_configuration_tests.adb
cmp /evidence/before-doc-comment/run_root_configuration_tests build/test-bin/run_root_configuration_tests
sha256sum build/test-bin/run_root_configuration_tests
