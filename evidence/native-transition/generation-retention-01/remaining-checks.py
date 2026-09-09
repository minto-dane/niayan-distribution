# SPDX-License-Identifier: MIT
import os,subprocess
from pathlib import Path
r=Path('/home/nia/devbox/niaos/nia-os-consent');w=r.parent/'.work/native-generation-retention-01'
def run(name,args,env=None):
 print('Starting '+name,flush=True)
 with (w/(name+'.log')).open('w') as f:
  subprocess.run(args,cwd=r,env={**os.environ,**(env or {})},stdout=f,stderr=subprocess.STDOUT,check=True)
 print('Passed '+name,flush=True)
run('build-comparison',['python3',str(w/'compare-builds.py')])
run('workspace-build-comparison',['python3',str(w/'compare-workspaces.py')])
run('accepted-build-test',['python3',str(w/'run-container.py'),'sh','pkgcore/ci/test-all.sh'],{'PROBE_COPY':'workspace'})
run('root-probe',['python3',str(w/'run-container.py'),'sh','pkgcore/ci/generation-root-refusal-test.sh'],{'PROBE_COPY':'workspace','PROBE_UID':'0:0'})
run('sanitized',['python3',str(w/'run-container.py'),'python3','/evidence/run-sanitized.py'],{'PROBE_COPY':'sanitized'})
run('source-check',['sh','dev/run-limited.sh','python3','assurance/ci/run-engineering-checks.py','--mode','source'])
