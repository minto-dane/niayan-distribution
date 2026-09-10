# SPDX-License-Identifier: MIT
import os
from pathlib import Path
import subprocess

work=Path(__file__).resolve().parent
root=Path('/home/nia/devbox/niaos/nia-os-consent')
subprocess.run(['sh',str(root/'dev/run-limited.sh'),'python3',str(work/'compare.py')],check=True,cwd=root)
def run(name,args):
    print('Starting '+name,flush=True)
    with (work/'chaos'/name).open('x') as log:
        subprocess.run(args,check=True,cwd=root,stdout=log,stderr=subprocess.STDOUT)
    print('Passed '+name,flush=True)
run('build.log',['python3',str(work/'run-chaos-container.py'),'gprbuild','-p','-P','/evidence/chaos/chaos.gpr','-j1'])
for number,seed in [(1,20260910),(2,20260911)]:
    run('attempt-%02d.log'%number,['python3',str(work/'run-chaos-container.py'),'env',
        'PYTHONPATH=/workspace/distribution/native:/workspace/distribution/tools:/workspace/distribution/tests',
        'python3','-B','/evidence/chaos/campaign.py','--seed',str(seed),'--output','/evidence/chaos/attempt-%02d'%number])
run('audit.log',['python3',str(work/'run-container.py'),'python3','-B','/evidence/audit-chaos.py'])
