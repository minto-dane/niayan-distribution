# SPDX-License-Identifier: BSD-3-Clause
import os,subprocess
from pathlib import Path
root=Path('/workspace/pkgcore');work=Path('/evidence')
subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-O1','-g','-fPIC','-shared','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(root/'runtime/root_handoff.c'),str(root/'runtime/root_handoff_wire.c'),'-lsodium','-o',str(work/'root-handoff-sanitizer.so')],check=True)
env=dict(os.environ,LD_PRELOAD=subprocess.check_output(['gcc','-print-file-name=libasan.so'],text=True).strip(),ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
subprocess.run(['python3',str(root/'tests/check_root_handoff.py'),str(work/'root_handoff.py'),str(work/'root-handoff-sanitizer.so'),str(root/'build/test-bin/run_root_handoff_tests'),str(work/'sanitizer.json')],env=env,check=True,timeout=60)
