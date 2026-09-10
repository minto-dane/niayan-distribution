# SPDX-License-Identifier: MIT
import os
from pathlib import Path
import subprocess

subprocess.run(['gprbuild','-s','-j1','-p','-P','tests.gpr','run_archive_supply_tests.adb',
                '-cargs:C','-fsanitize=address,undefined','-fno-omit-frame-pointer',
                '-largs','-fsanitize=address,undefined'],check=True)
store=Path('/evidence/sanitized-test-store');store.mkdir(mode=0o700)
env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0:halt_on_error=1',
     'UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
driver='/workspace/pkgcore/build/test-bin/run_archive_supply_tests'
subprocess.run([driver,str(store),'/workspace/pkgcore/tests/fixtures/selected-catalog'],env=env,check=True)
subprocess.run(['python3','-B','/workspace/distribution/native/check_archive_receipt_bridge.py',
                '--driver',driver],env=env,check=True)
