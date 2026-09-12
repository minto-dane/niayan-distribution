# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import subprocess,json,os
os.umask(0o077)
root=Path('/workspace/pkgcore');lab=Path('/evidence');out=lab/'native-check-02';out.mkdir()
commands=[['build/test-bin/run_root_handoff_tests'],['build/test-bin/run_root_archive_tests',str(out/'archive/store'),'tests/fixtures/root-archive'],['build/test-bin/run_conffile_observation_tests',str(out/'configured/store'),str(out/'configured/root'),'tests/fixtures/root-archive']]
for name in ['archive/store','configured/store','configured/root']:(out/name).mkdir(parents=True,exist_ok=True)
results=[]
for index,command in enumerate(commands):
 with (out/(str(index)+'.log')).open('w') as log:subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
 results.append(command[0]);print('PASS',command[0],flush=True)
(out/'report.json').write_text(json.dumps(dict(result='pass',mains=results,scope='new Ada API and v5/v6 native stage transport boundary regressions; synthetic authority, no physical extraction'),indent=2)+'\n')
