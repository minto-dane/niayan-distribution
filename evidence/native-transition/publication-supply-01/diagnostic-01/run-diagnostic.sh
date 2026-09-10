#!/bin/sh
set -eu
cd /workspace/pkgcore
mkdir -p /evidence/diagnostic-01-run/map /evidence/diagnostic-01-run/publication/root /evidence/diagnostic-01-run/publication/state /evidence/diagnostic-01-run/publication/store /evidence/diagnostic-01-run/publication/bank
chmod 700 /evidence/diagnostic-01-run /evidence/diagnostic-01-run/map /evidence/diagnostic-01-run/publication /evidence/diagnostic-01-run/publication/*
timeout --kill-after=5s 600s build/test-bin/run_supply_map_tests /evidence/diagnostic-01-run/map tests/fixtures/selected-catalog > /evidence/diagnostic-01-map.log 2>&1
timeout --kill-after=5s 600s build/test-bin/run_generation_publication_tests /evidence/diagnostic-01-run/publication/root /evidence/diagnostic-01-run/publication/state /evidence/diagnostic-01-run/publication/store /evidence/diagnostic-01-run/publication/bank /workspace/pkgcore/tests/fixtures/selected-catalog > /evidence/diagnostic-01-publication.log 2>&1
