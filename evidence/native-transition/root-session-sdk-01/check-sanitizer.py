# SPDX-License-Identifier: BSD-3-Clause
import os,subprocess
from pathlib import Path
subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-O1','-g','-fPIC','-shared','-fsanitize=address,undefined','-fno-omit-frame-pointer','runtime/root_session.c','-o','/evidence/root-session-sanitizer.so'],check=True)
as_runtime=subprocess.check_output(['cc','-print-file-name=libasan.so'],text=True).strip()
env=dict(os.environ,LD_PRELOAD=as_runtime,ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
subprocess.run(['python3','tests/check_root_session_transport.py','--library','/evidence/root-session-sanitizer.so','--report','/evidence/sanitizer.json'],env=env,check=True,timeout=60)
