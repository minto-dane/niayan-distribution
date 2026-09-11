#!/bin/sh
set -eu
cd /workspace/pkgcore
gprbuild -f -P tests.gpr -j1 run_generation_publication_tests.adb
python3 -B tests/check_configured_publication.py --driver build/test-bin/run_generation_publication_tests --case /evidence/configured-02 > /evidence/configured-02.log 2>&1
cat /evidence/configured-02.log
python3 -B tests/check_root_publication.py --driver build/test-bin/run_generation_publication_tests > /evidence/root-publication-02.log 2>&1
cat /evidence/root-publication-02.log
build/test-bin/run_generation_publication_tests /evidence/publication-01/root /evidence/publication-01/state /evidence/publication-01/store /evidence/publication-01/bank /workspace/pkgcore/tests/fixtures/selected-catalog > /evidence/publication-02.log 2>&1
cat /evidence/publication-02.log
build/test-bin/run_generation_stage_tests /evidence/stage-01/root /evidence/stage-01/state /evidence/stage-01/store > /evidence/stage-02.log 2>&1
cat /evidence/stage-02.log
build/test-bin/run_root_configuration_tests /evidence/root-01/store /evidence/root-01/root /workspace/pkgcore/tests/fixtures/conffiles > /evidence/root-02.log 2>&1
cat /evidence/root-02.log
python3 -B tests/check_configured_root_current.py --native /evidence/root-02.log --cas /evidence/root-01/store --root /evidence/root-01/root --driver /workspace/pkgcore/build/test-bin/run_root_configuration_tests --output /evidence/current-oracle-02
