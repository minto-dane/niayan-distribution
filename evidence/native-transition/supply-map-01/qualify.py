# SPDX-License-Identifier: MIT
"""Run the actual supply/native bridge and complete bounded integration gates."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

root=Path('/home/nia/devbox/niaos/nia-os-consent');work=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'assurance/ci'))
import engineering
subject=engineering.source_subject(root)
assert engineering.source_subject(work/'workspace')==subject
report={'result':'running','source_subject':subject,'image':(work/'dev-image.id').read_text().strip(),
        'checks':[],'production_approval':False,'formal_proof':'not-repeated-input-comparison-required'}
def run(name,args,env=None):
    print('Starting '+name,flush=True)
    with (work/(name+'.log')).open('x') as output:
        result=subprocess.run(args,cwd=root,env={**os.environ,**(env or {})},stdout=output,stderr=subprocess.STDOUT)
    report['checks'].append({'name':name,'returncode':result.returncode,
        'log_sha256':hashlib.sha256((work/(name+'.log')).read_bytes()).hexdigest()})
    (work/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
    if result.returncode:raise SystemExit(result.returncode)
    print('Passed '+name,flush=True)
def container(name,command,env=None):
    run(name,['python3','-B',str(work/'run-container.py'),*command],env)
container('image-packages',['sh','-ec',
    "python3 -c 'import tuf, securesystemslib; print(tuf.__version__, securesystemslib.__version__)'; dpkg-query -W"])
container('workspace-check',['make','check','private-dbus','JOBS=1'])
container('native-image-check',['make','image-check'],{'PROBE_CWD':'/workspace/distribution',
    'PROBE_IMAGE':'sha256:b626ca976c8ba342df3377e3ad068e29bf45b4c3ad0f7f8927f0551dd09c07dd'})
container('independent-build',['make','build','JOBS=1'],{'PROBE_TREE':'independent-long-path',
    'PROBE_MOUNT':'/independent-long-workspace','PROBE_TZ':'Pacific/Honolulu','PROBE_SOURCE_EPOCH':'1788739200'})
container('independent-test-build',['make','-C','pkgcore','test-build','JOBS=1'],{'PROBE_TREE':'independent-long-path',
    'PROBE_MOUNT':'/independent-long-workspace','PROBE_TZ':'Pacific/Honolulu','PROBE_SOURCE_EPOCH':'1788739200'})
container('pkgcore-independent-ci',['sh','pkgcore/ci/test-all.sh'])
container('root-refusal',['sh','pkgcore/ci/generation-root-refusal-test.sh'],{'PROBE_UID':'0:0'})
container('issuer-root-refusal',['python3','-B','-c',
    "import os,sys;sys.path[:0]=['distribution/native','distribution/tools'];from archive_receipt import issue;from nia_common import Invalid;assert os.geteuid()==0\ntry: issue(None,None,None,None,None,None,minimum_security_epoch=1,maximum_lifetime_seconds=1,public_key=b'',sign=None)\nexcept Invalid as e: assert str(e)=='unprivileged archive receipt issuer required';print('PASS real UID0 issuer refusal before supply or signing')\nelse: raise AssertionError('root accepted')"],{'PROBE_UID':'0:0'})
container('sanitized',['python3','/evidence/run-sanitized.py'],{'PROBE_TREE':'sanitized','PROBE_CWD':'/workspace/pkgcore'})
run('host-source-check',['sh','dev/run-limited.sh','python3','-B','assurance/ci/run-engineering-checks.py','--mode','source'])
run('engineering-lint',['sh','dev/run-limited.sh','python3','-B','assurance/ci/engineering.py','lint'])
assert engineering.source_subject(root)==subject
assert engineering.source_subject(work/'workspace')==subject
assert engineering.source_subject(work/'independent-long-path')==subject
report['result']='pass';report['source_subject_after']=subject
(work/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS all requested gates; source subject '+subject,flush=True)
