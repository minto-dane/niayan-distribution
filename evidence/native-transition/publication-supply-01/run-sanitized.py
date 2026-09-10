# SPDX-License-Identifier: MIT
import os
from pathlib import Path
import subprocess

subprocess.run(['gprbuild','-s','-j1','-p','-P','tests.gpr','run_supply_map_tests.adb',
                'run_generation_publication_tests.adb','run_generation_stage_tests.adb',
                '-cargs:C','-fsanitize=address,undefined','-fno-omit-frame-pointer',
                '-largs','-fsanitize=address,undefined'],check=True)
env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0:halt_on_error=1',
     'UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
base=Path('/evidence/sanitized-run');base.mkdir(mode=0o700)
for name in ['map','publication/root','publication/state','publication/store','publication/bank','stage/root','stage/state','stage/store']:
    path=base/name;path.mkdir(parents=True,mode=0o700);path.chmod(0o700)
def run(command): subprocess.run(command,env=env,check=True,timeout=600)
prefix='/workspace/pkgcore/build/test-bin/'
run([prefix+'run_supply_map_tests',str(base/'map'),'/workspace/pkgcore/tests/fixtures/selected-catalog'])
run([prefix+'run_generation_stage_tests',*[str(base/'stage'/n) for n in ['root','state','store']]])
run([prefix+'run_generation_publication_tests',*[str(base/'publication'/n) for n in ['root','state','store','bank']],
     '/workspace/pkgcore/tests/fixtures/selected-catalog'])
run(['python3','-B','/workspace/distribution/native/check_supply_map_bridge.py',
     '--driver',prefix+'run_supply_map_tests'])
