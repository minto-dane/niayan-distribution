# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import hashlib,json,subprocess
lab=Path(__file__).resolve().parent;root=Path('/home/nia/devbox/niaos/nia-os-consent')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs={}
for part in ['src','runtime','vendor','tests']:
 for p in sorted((root/'pkgcore'/part).rglob('*')):
  if p.is_file() and p.suffix in ('.ads','.adb','.c','.h'):
   relative=p.relative_to(root/'pkgcore');assert p.stat().st_size<1024*1024
   assert p.read_bytes()==(lab/'workspace/pkgcore'/relative).read_bytes(),relative
   inputs['pkgcore/'+relative.as_posix()]=sha(p)
for name in ['tests.gpr']:
 p=root/'pkgcore'/name;assert p.read_bytes()==(lab/'workspace/pkgcore'/name).read_bytes();inputs['pkgcore/'+name]=sha(p)
fixtures={}
for folder in ['conffiles','root-preparation']:
 for p in sorted((root/'pkgcore/tests/fixtures'/folder).rglob('*')):
  if p.is_file():
   relative=p.relative_to(root/'pkgcore');assert p.stat().st_size<1024*1024
   assert p.read_bytes()==(lab/'workspace/pkgcore'/relative).read_bytes()
   fixtures['pkgcore/'+relative.as_posix()]=sha(p)
tools={}
for name in ['root_bank.py','worker/check_root_preparation.py','worker/check_root_reinspection.py','worker/check_root_extract.py']:
 p=root/'distribution/native'/name;assert p.read_bytes()==(lab/'workspace/native'/name).read_bytes();tools['distribution/native/'+name]=sha(p)
unchanged=[]
for repo in ['assurance','pkgcore','statecore','controlcore','configcore','resolvercore','capsulecore']:
 for p in (root/repo/'src').glob('*'):
  if not p.is_file():continue
  committed=subprocess.check_output(['git','show','HEAD:src/'+p.name],cwd=root/repo)
  assert p.read_bytes()==committed,p
 unchanged.append(repo)
(lab/'source-provenance.json').write_text(json.dumps(dict(result='pass',compile_inputs=inputs,fixtures=fixtures,vm_tools=tools,mathematical_src_repositories_unchanged=unchanged),indent=2)+'\n')
print('PASS',len(inputs),'compile inputs,',len(fixtures),'fixtures,',len(tools),'VM tools; seven mathematical src trees unchanged')
