# SPDX-License-Identifier: MIT
import os,subprocess
from pathlib import Path
root=Path('/home/nia/devbox/niaos/nia-os-consent');work=root.parent/'.work/native-archive-supply-01'
steps=[('native-image-check',['make','image-check'],{'PROBE_IMAGE':'native','PROBE_CWD':'/workspace/distribution'}),
       ('official-offline-replay',['python3','-B','/evidence/replay-official.py'],{'PROBE_IMAGE':'native'}),
       ('root-refusal',['python3','-B','-c',"import os,sys;sys.path[:0]=['/workspace/distribution/native','/workspace/distribution/tools'];from archive_intake import authenticate;from nia_common import Invalid;assert os.geteuid()==0\ntry: authenticate(None,None,None,None,None,None,minimum_security_epoch=1)\nexcept Invalid as e: assert str(e)=='unprivileged archive intake required';print('PASS real UID0 refusal before supply access')\nelse: raise AssertionError('root accepted')"],{'PROBE_IMAGE':'native','PROBE_UID':'0:0'}),
       ('download-cli',['python3','-B','native/check_download_cli.py'],{'PROBE_IMAGE':'native','PROBE_UID':'0:0','PROBE_CWD':'/workspace/distribution'}),
       ('container-source-check',['python3','-B','assurance/ci/run-engineering-checks.py','--mode','source'],{})]
for name,args,env in steps:
    print('Starting '+name,flush=True)
    with (work/(name+'.log')).open('w') as output:
        subprocess.run(['python3',str(work/'run-container.py'),*args],stdout=output,stderr=subprocess.STDOUT,
                       env={**os.environ,**env},check=True)
    print('Passed '+name,flush=True)
print('Starting host-source-check',flush=True)
with (work/'host-source-check.log').open('w') as output:
    subprocess.run(['sh','dev/run-limited.sh','python3','-B','assurance/ci/run-engineering-checks.py','--mode','source'],
                   cwd=root,stdout=output,stderr=subprocess.STDOUT,check=True)
print('Passed host-source-check',flush=True)
