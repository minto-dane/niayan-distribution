# SPDX-License-Identifier: MIT
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

root=Path('/home/nia/devbox/niaos/nia-os-consent');work=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'assurance/ci'))
import engineering
inputs=json.loads((work/'workspace-inputs.json').read_text())
excluded={'.git','build','evidence','__pycache__','.pytest_cache'}
def inventory(tree):
    result={}
    for parent,dirs,files in os.walk(tree,followlinks=False):
        dirs[:]=sorted(d for d in dirs if d not in excluded)
        for name in sorted(files):
            if name in excluded or name.endswith('.pyc'):continue
            p=Path(parent)/name
            assert not p.is_symlink() and p.stat().st_size<=8*1024*1024,p
            result[str(p.relative_to(tree))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result
copies=[]
for tree in (root,work/'workspace',work/'independent-long-path'):
    assert inventory(tree)==inputs,tree
    copies.append({'path':str(tree),'inputs':len(inputs),'matches':True})
sanitized={p:h for p,h in inputs.items() if p.startswith(('pkgcore/','distribution/'))}
assert inventory(work/'sanitized')==sanitized
copies.append({'path':str(work/'sanitized'),'inputs':len(sanitized),'matches':True})
(work/'input-comparison.json').write_text(json.dumps({'result':'pass','copies':copies},indent=2)+'\n')

def binaries(tree):
    return {str(p.relative_to(tree)):hashlib.sha256(p.read_bytes()).hexdigest()
            for name in ('build/bin','build/test-bin') for p in sorted((tree/name).iterdir()) if p.is_file()}
first=work/'workspace';second=work/'independent-long-path'
a,b=binaries(first/'pkgcore'),binaries(second/'pkgcore')
assert len(a)==30 and a==b
applications=[]
for repo in engineering.REPOS:
    artifact=json.loads((root/repo/'packaging/nia/artifact.json').read_text())
    for entry in artifact['executables']:
        name=repo+'/'+entry['source']
        digest=hashlib.sha256((first/name).read_bytes()).hexdigest()
        assert hashlib.sha256((second/name).read_bytes()).hexdigest()==digest,name
        applications.append({'path':name,'sha256':digest})
assert len(applications)==18
elf=[]
for name,digest in a.items():
    text=subprocess.check_output(['readelf','-W','-h','-l','-d',str(first/'pkgcore'/name)],text=True)
    props={'pie':bool(re.search(r'Type:\s+DYN\b',text)) and bool(re.search(r'FLAGS_1.*PIE',text)),
      'non_executable_stack':any(l.split()[0]=='GNU_STACK' and 'E' not in ''.join(l.split()[6:-1]) for l in text.splitlines() if l.split()),
      'relro':'GNU_RELRO' in text,'bind_now':'BIND_NOW' in text or bool(re.search(r'FLAGS_1.*NOW',text)),
      'no_writable_executable_load':not any(l.split()[0]=='LOAD' and all(flag in ''.join(l.split()[6:-1]) for flag in 'WE') for l in text.splitlines() if l.split())}
    assert all(props.values()),(name,props)
    elf.append({'path':name,'sha256':digest,'properties':props})
(work/'reproducibility.json').write_text(json.dumps({'result':'identical-binaries','pkgcore_binary_count':30,
  'pkgcore_binaries':a,'application_count':18,'applications':applications,
  'paths':['/workspace','/independent-long-workspace'],'source_date_epoch':[None,1788739200],
  'timezones':['UTC (build runner cleans TZ)','Pacific/Honolulu'],'second_input_mtime':1788652800,'jobs':[1,1]},indent=2)+'\n')
(work/'elf.json').write_text(json.dumps({'result':'pass','checks':elf},indent=2)+'\n')
baseline=root/'assurance/evidence/native-development/current-component-proof/report.json'
proofs=[]
for row in json.loads(baseline.read_text())['components']:
    repo=row['repository'];expected=row['proof_inputs']
    for name,digest in expected.items():
        assert hashlib.sha256((root/repo/name).read_bytes()).hexdigest()==digest,(repo,name)
    gpr=(root/repo/'proof.gpr').read_text()
    dirs=re.findall(r'"([^"]+)"',re.search(r'for Source_Dirs use\s*\((.*?)\)',gpr,re.S).group(1))
    actual={str(p.relative_to(root/repo)) for d in dirs for p in (root/repo/d).iterdir() if p.suffix in ('.ads','.adb')}
    assert actual=={p for p in expected if Path(p).suffix in ('.ads','.adb')}
    proofs.append({'repository':repo,'input_count':len(expected),'unchanged':True})
assert len(proofs)==7
(work/'proof-input-comparison.json').write_text(json.dumps({'result':'unchanged','baseline':str(baseline.relative_to(root)),
  'baseline_sha256':hashlib.sha256(baseline.read_bytes()).hexdigest(),'components':proofs,
  'formal_proof_repeated':False,'new_runtime_is_spark':False},indent=2)+'\n')
print('PASS 30 pkgcore executables and 18 applications identical; 30 ELF checks; exact source copies; seven unchanged mathematical input sets')
