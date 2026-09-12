# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import subprocess
root=Path('/workspace');lab=Path('/evidence')
commands=[(['gprbuild','-P','tests.gpr','-p','-j1','run_root_handoff_tests.adb'],root/'pkgcore'),
 (['gcc','-std=c11','-Wall','-Wextra','-Werror','-O1','-g','-fPIC','-shared','-fstack-protector-strong','-D_FORTIFY_SOURCE=3','-Wl,-z,relro,-z,now,-z,noexecstack','runtime/root_handoff.c','runtime/root_handoff_wire.c','-lsodium','-o','/evidence/root-handoff.so'],root/'pkgcore'),
 (['python3','-m','mypy','--config-file','native/handoff-mypy.ini','--no-incremental','native/root_handoff.py'],root/'distribution'),
 (['python3','dev/c-proof.py','--output','/evidence/proof'],root)]
for index,(command,cwd) in enumerate(commands):
 with (lab/(str(index)+'.log')).open('w') as log:
  subprocess.run(command,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 print('PASS',index,flush=True)
