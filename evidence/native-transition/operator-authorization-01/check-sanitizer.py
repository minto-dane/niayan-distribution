# SPDX-License-Identifier: BSD-3-Clause
import os,subprocess
subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-O1','-g','-fPIC','-shared','-fsanitize=address,undefined','-fno-omit-frame-pointer','runtime/operator_authorization.c','-lsystemd','-o','/evidence/operator-sanitizer.so'],check=True)
runtime=subprocess.check_output(['cc','-print-file-name=libasan.so'],text=True).strip()
env=dict(os.environ,LD_PRELOAD=runtime,ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
subprocess.run(['python3','tests/check_operator_transport.py','--library','/evidence/operator-sanitizer.so','--authority','/evidence/operator-authority-fixture','--vm-helper','/evidence/check_operator_authorization.py','--report','/evidence/sanitizer.json'],env=env,check=True,timeout=60)
