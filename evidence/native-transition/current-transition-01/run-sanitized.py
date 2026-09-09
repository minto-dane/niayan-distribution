# SPDX-License-Identifier: MIT
import os, subprocess
from pathlib import Path
subprocess.run(['gprbuild', '-s', '-j1', '-p', '-P', 'tests.gpr', 'run_generation_publication_tests.adb', '-cargs:C', '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-largs', '-fsanitize=address,undefined'], check=True)
base = Path('/evidence/sanitized-fixtures')
base.mkdir(mode=0o700)
names = ['pub-root', 'pub-state', 'pub-cas', 'pub-bank']
for name in names:
    (base / name).mkdir(mode=0o700)
env = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:halt_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
subprocess.run(['timeout', '--kill-after=5s', '600s', '/workspace/build/test-bin/run_generation_publication_tests', *[str(base / name) for name in names], '/workspace/tests/fixtures/selected-catalog'], env=env, check=True)
