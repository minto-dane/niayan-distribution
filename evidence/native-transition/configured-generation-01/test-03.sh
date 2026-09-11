#!/bin/sh
set -eu
cd /workspace/pkgcore
gprbuild -f -P tests.gpr -j1 run_root_configuration_tests.adb run_root_archive_tests.adb
build/test-bin/run_root_configuration_tests /evidence/root-02/store /evidence/root-02/root /workspace/pkgcore/tests/fixtures/conffiles > /evidence/root-test-02.log 2>&1
cat /evidence/root-test-02.log
python3 -B tests/check_configured_root_current.py --native /evidence/root-test-02.log --cas /evidence/root-02/store --root /evidence/root-02/root --driver /workspace/pkgcore/build/test-bin/run_root_configuration_tests --output /evidence/current-oracle-02
python3 -B tests/check_configured_root.py --native /evidence/root-test-02.log --cas /evidence/root-02/store --output /evidence/root-oracle-02
build/test-bin/run_generation_publication_tests /evidence/publication-01/root /evidence/publication-01/state /evidence/publication-01/store /evidence/publication-01/bank /workspace/pkgcore/tests/fixtures/root-archive root-archive > /evidence/publication-test-01.log 2>&1
cat /evidence/publication-test-01.log
python3 -B /evidence/publication-oracle.py
python3 /evidence/package-runtime.py
