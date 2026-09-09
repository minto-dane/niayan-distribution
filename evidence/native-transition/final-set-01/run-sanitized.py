# SPDX-License-Identifier: MIT
import os,subprocess
subprocess.run(['gprbuild','-s','-j1','-p','-P','tests.gpr','run_deb_final_set_tests.adb','-cargs:C','-fsanitize=address,undefined','-fno-omit-frame-pointer','-largs','-fsanitize=address,undefined'],check=True)
subprocess.run(['/workspace/build/test-bin/run_deb_final_set_tests','/evidence/sanitized-cas','/workspace/tests/fixtures/deb-final-set'],env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'},check=True)
