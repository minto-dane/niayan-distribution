# SPDX-License-Identifier: MIT
import hashlib,json,re,subprocess
from pathlib import Path
base=Path('/home/nia/devbox/niaos/.work/native-catalog-retention-01'); root=Path('/home/nia/devbox/niaos/nia-os-consent')
first=base/'workspace/pkgcore';second=base/'workspace-independent-long-path/pkgcore'
def binaries(tree):
 return {str(p.relative_to(tree)): hashlib.sha256(p.read_bytes()).hexdigest() for sub in ['build/bin','build/test-bin'] for p in sorted((tree/sub).iterdir()) if p.is_file()}
a=binaries(first);b=binaries(second);assert len(a)==29 and a==b
(base/'reproducibility.json').write_text(json.dumps(dict(result='identical-binaries',binary_count=len(a),first_path='/workspace/pkgcore',second_path='/independent/workspace/pkgcore',first_mtimes='preserved checkout mtimes',second_mtime=1788652800,timezones=['UTC system default; TZ removed by build runner','Pacific/Honolulu'],source_date_epoch=[None,1788739200],binaries=a),indent=2)+'\n')
rows=[]
for name,h in a.items():
 text=subprocess.check_output(['readelf','-W','-h','-l','-d',str(first/name)],text=True)
 props=dict(pie=bool(re.search(r'Type:\s+DYN\b',text)) and bool(re.search(r'FLAGS_1.*PIE',text)),non_executable_stack=any(l.split()[0]=='GNU_STACK' and 'E' not in ''.join(l.split()[6:-1]) for l in text.splitlines() if l.split()),relro='GNU_RELRO' in text,bind_now='BIND_NOW' in text or bool(re.search(r'FLAGS_1.*NOW',text)),no_writable_executable_load=not any(l.split()[0]=='LOAD' and all(flag in ''.join(l.split()[6:-1]) for flag in 'WE') for l in text.splitlines() if l.split()))
 assert all(props.values()),(name,props)
 rows.append(dict(name=name,sha256=h,properties=props,result='pass'))
(base/'elf.json').write_text(json.dumps(dict(result='pass',checks=rows),indent=2)+'\n')
inputs=json.loads((base/'build-inputs.json').read_text()); rows=[]
for tree in [root/'pkgcore',first,second,base/'sanitized']:
 actual={str(p.relative_to(tree)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tree.rglob('*') if p.is_file() and not set(p.relative_to(tree).parts)&{'.git','build','evidence','__pycache__'}}
 assert actual==inputs,(tree,set(inputs)^set(actual)); rows.append(dict(path=str(tree),input_count=len(actual),matches=True))
(base/'input-comparison.json').write_text(json.dumps(dict(result='pass',copies=rows),indent=2)+'\n')
print('29 identical executables; 29 ELF hardening checks;',len(inputs),'inputs match every copy')
