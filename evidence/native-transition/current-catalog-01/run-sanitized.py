# SPDX-License-Identifier: MIT
import os,subprocess
from pathlib import Path
subprocess.run(['gprbuild','-s','-j1','-p','-P','tests.gpr','run_generation_publication_tests.adb','-cargs:C','-fsanitize=address,undefined','-fno-omit-frame-pointer','-largs','-fsanitize=address,undefined'],check=True)
paths=['/evidence/sanitized-'+name for name in ['root','state','cas','bank']]
for path in paths:Path(path).mkdir(mode=0o700)
subprocess.run(['/workspace/build/test-bin/run_generation_publication_tests',*paths,'/workspace/tests/fixtures/selected-catalog'],env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'},check=True)
