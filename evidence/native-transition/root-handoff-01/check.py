# SPDX-License-Identifier: BSD-3-Clause
import subprocess
from pathlib import Path
root=Path('/workspace/pkgcore');work=Path('/evidence')
subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-O1','-g','-fPIC','-shared','-fstack-protector-strong','-D_FORTIFY_SOURCE=3','-Wl,-z,relro,-z,now,-z,noexecstack','-ffile-prefix-map='+str(root)+'=/usr/src/niaos/pkgcore/',str(root/'runtime/root_handoff.c'),'-lsodium','-o',str(work/'root-handoff.so')],check=True)
subprocess.run(['python3',str(root/'tests/check_root_handoff.py'),str(work/'root_handoff.py'),str(work/'root-handoff.so'),str(root/'build/test-bin/run_root_handoff_tests'),str(work/'transport-01.json')],check=True,timeout=60)
