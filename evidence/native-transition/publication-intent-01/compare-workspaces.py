# SPDX-License-Identifier: MIT
import hashlib, json, re, subprocess
from pathlib import Path
w=Path('/home/nia/devbox/niaos/.work/native-publication-intent-01');root=Path('/home/nia/devbox/niaos/nia-os-consent')
first=w/'workspace';second=w/'workspace-independent-long-path'
expected=json.loads((w/'workspace-inputs.json').read_text());copies=[]
for tree in [root,first,second]:
 actual={str(p.relative_to(tree)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tree.rglob('*') if p.is_file() and not set(p.relative_to(tree).parts)&{'.git','build','evidence','__pycache__'}}
 assert actual==expected,(tree,set(actual)^set(expected),[k for k in set(actual)&set(expected) if actual[k]!=expected[k]])
 copies.append(dict(path=str(tree),inputs=len(actual),matches=True))
repos=['assurance','pkgcore','statecore','controlcore','configcore','resolvercore','capsulecore'];binaries={};elf=[]
for repo in repos:
 artifact=json.loads((root/repo/'packaging/nia/artifact.json').read_text())
 for executable in artifact['executables']:
  name=repo+'/'+executable['source'];a=(first/name).read_bytes();b=(second/name).read_bytes();assert a==b,name
  binaries[name]=hashlib.sha256(a).hexdigest()
  output=subprocess.check_output(['readelf','-W','-h','-l','-d',str(first/name)],text=True)
  props=dict(pie=bool(re.search(r'Type:\s+DYN\b',output)) and bool(re.search(r'FLAGS_1.*PIE',output)),non_executable_stack=any(l.split()[0]=='GNU_STACK' and 'E' not in ''.join(l.split()[6:-1]) for l in output.splitlines() if l.split()),relro='GNU_RELRO' in output,bind_now='BIND_NOW' in output or bool(re.search(r'FLAGS_1.*NOW',output)),no_writable_executable_load=not any(l.split()[0]=='LOAD' and all(flag in ''.join(l.split()[6:-1]) for flag in 'WE') for l in output.splitlines() if l.split()))
  assert all(props.values()),(name,props);elf.append(dict(name=name,sha256=binaries[name],properties=props))
assert len(binaries)==18
(w/'workspace-reproducibility.json').write_text(json.dumps(dict(result='identical-binaries',binary_count=18,binaries=binaries,input_copies=copies,elf=elf,source_date_epoch=[None,1788739200],independent_mtime=1788652800,timezones=['UTC system default; TZ unset','Pacific/Honolulu'],jobs=1,first_environment='run-engineering-checks removes SOURCE_DATE_EPOCH and TZ; JOBS=1'),indent=2)+'\n')
print('18 whole-workspace binaries identical; all ELF checks pass;',len(expected),'inputs identical in three trees')
