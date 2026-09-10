#!/bin/sh
set -eu
cd /workspace/pkgcore
mkdir -p /evidence/diagnostic-03-run/map /evidence/diagnostic-03-run/publication/root /evidence/diagnostic-03-run/publication/state /evidence/diagnostic-03-run/publication/store /evidence/diagnostic-03-run/publication/bank
chmod 700 /evidence/diagnostic-03-run /evidence/diagnostic-03-run/map /evidence/diagnostic-03-run/publication /evidence/diagnostic-03-run/publication/*
timeout --kill-after=5s 600s build/test-bin/run_supply_map_tests /evidence/diagnostic-03-run/map tests/fixtures/selected-catalog > /evidence/diagnostic-03-map.log 2>&1
timeout --kill-after=5s 600s build/test-bin/run_generation_publication_tests /evidence/diagnostic-03-run/publication/root /evidence/diagnostic-03-run/publication/state /evidence/diagnostic-03-run/publication/store /evidence/diagnostic-03-run/publication/bank /workspace/pkgcore/tests/fixtures/selected-catalog > /evidence/diagnostic-03-publication.log 2>&1
python3 -B tests/compare_current_catalog.py --root /evidence/diagnostic-03-run/publication/root --state /evidence/diagnostic-03-run/publication/state --cas /evidence/diagnostic-03-run/publication/store --bank /evidence/diagnostic-03-run/publication/bank --media tests/fixtures/selected-catalog --native /evidence/diagnostic-03-publication.log --output /evidence/diagnostic-03-oracle.json > /evidence/diagnostic-03-oracle.log 2>&1
mkdir -p /evidence/diagnostic-03-run/stage/root /evidence/diagnostic-03-run/stage/state /evidence/diagnostic-03-run/stage/store
chmod 700 /evidence/diagnostic-03-run/stage /evidence/diagnostic-03-run/stage/*
timeout --kill-after=5s 600s build/test-bin/run_generation_stage_tests /evidence/diagnostic-03-run/stage/root /evidence/diagnostic-03-run/stage/state /evidence/diagnostic-03-run/stage/store > /evidence/diagnostic-03-stage.log 2>&1
