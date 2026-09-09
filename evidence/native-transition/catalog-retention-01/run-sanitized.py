# SPDX-License-Identifier: MIT
import os, subprocess
from pathlib import Path
subprocess.run(['gprbuild','-s','-j1','-p','-P','tests.gpr','run_catalog_store_tests.adb','-cargs:C','-fsanitize=address,undefined','-fno-omit-frame-pointer','-largs','-fsanitize=address,undefined'],check=True)
Path('/evidence/sanitized-cas').mkdir(mode=0o700)
subprocess.run(['/workspace/build/test-bin/run_catalog_store_tests','/evidence/sanitized-cas','/workspace/tests/fixtures/selected-catalog'],env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'},check=True)
