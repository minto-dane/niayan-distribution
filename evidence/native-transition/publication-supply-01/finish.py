# SPDX-License-Identifier: MIT
"""Sequential post-qualification reproducibility and private publication fault runs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

work=Path(__file__).resolve().parent
root=Path('/home/nia/devbox/niaos/nia-os-consent')
sys.path.insert(0,str(root/'assurance/ci'));import engineering
qualification=json.loads((work/'qualification.json').read_text())
assert qualification['result']=='pass'
subject=qualification['source_subject'];assert engineering.source_subject(root)==subject
# Source and binaries are unchanged; successful comparison evidence is retained.
assert json.loads((work/'reproducibility.json').read_text())['result']=='identical-binaries'

for number,seed in [(2,20260910),(3,20260911)]:
    name='attempt-%02d'%number
    assert not (work/'chaos'/name).exists()
    print('Starting publication '+name,flush=True)
    command=['python3',str(work/'run-chaos-container.py'),'python3','-B','/evidence/chaos/campaign.py',
             '--seed',str(seed),'--output','/evidence/chaos/'+name]
    with (work/'chaos'/(name+'.log')).open('x') as log:
        result=subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT)
    destination=work/'chaos'/name
    if destination.is_dir():
        shutil.copyfile(work/'chaos/campaign.py',destination/'campaign.py')
        (destination/'execution.json').write_text(json.dumps(dict(source_subject=subject,
          image=qualification['image'],uid=1000,network='none',lab_capabilities=['SYS_PTRACE','DAC_READ_SEARCH'],
          kernel_limits=dict(memory_bytes=3221225472,swap_bytes=0,cpu_cores=1,pids=128),
          command=command,returncode=result.returncode,
          sources={name:hashlib.sha256((work/name).read_bytes()).hexdigest() for name in ['chaos/campaign.py','run-chaos-container.py']}),indent=2)+'\n')
    assert result.returncode==0,name
    print('Passed publication '+name,flush=True)
with (work/'chaos/audit.log').open('x') as log:
    subprocess.run(['python3',str(work/'run-container.py'),'python3','-B','/evidence/audit-chaos.py'],
                   cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
assert engineering.source_subject(root)==subject
print('PASS publication fault runs and independent artifact readback',flush=True)
