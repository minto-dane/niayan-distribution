# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import hashlib,json,tarfile,stat
root=Path('/home/nia/devbox/niaos/nia-os-consent');lab=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
old=json.loads((lab.parent/'native-root-reinspection-sdk-01/source-provenance.json').read_text())
for section in ('compile_inputs','fixtures'):
 for name,digest in old[section].items():assert sha((root/name).read_bytes())==digest,name
manifest=json.loads((lab/'package-source/source-inputs.json').read_text())['files']
with tarfile.open(lab/'vm-package-01/packages/niaos-root-preparation_0.4.0.tar.xz') as source:
 members={m.name:m for m in source.getmembers() if m.isfile()}
 for relative,item in manifest.items():
  raw=(root/'distribution'/item['source']).read_bytes()
  assert sha(raw)==item['sha256'] and raw==(lab/'package-source'/relative).read_bytes(),relative
  selected=[n for n in members if n.endswith('/'+relative)]
  assert len(selected)==1,relative
  member=members[selected[0]]
  assert source.extractfile(member).read()==raw and stat.S_IMODE(member.mode)==item['mode'],relative
runtime=json.loads((lab/'sdk-runtime-inputs.json').read_text());checked={}
with tarfile.open(lab/'package-input-03.tar') as bundle:
 for member in bundle.getmembers():
  if not member.isfile():continue
  name=member.name;raw=bundle.extractfile(member).read();digest=sha(raw)
  if name.startswith('tests/'):
   assert raw==(root/'distribution/native'/name.removeprefix('tests/')).read_bytes(),name
  elif name.startswith('drivers/'):
   assert digest==runtime['drivers'][name.removeprefix('drivers/')],name
  elif name.startswith('lib/'):
   assert digest==runtime['libraries'][name.removeprefix('lib/')],name
  elif name.startswith('fixtures-'):
   variant,relative=name.split('/',1)
   base='conffiles' if variant=='fixtures-configured' else 'root-preparation'
   assert raw==(root/'pkgcore/tests/fixtures'/base/relative).read_bytes(),name
  elif name.startswith('source/'):
   assert raw==(lab/'package-source'/name.removeprefix('source/')).read_bytes(),name
  elif name=='service.deb':
   assert raw==(lab/'vm-package-01/packages/niaos-root-preparation_0.4.0_amd64.deb').read_bytes()
  else:raise AssertionError(name)
  checked[name]=digest
for line in (lab/'vm-package-01/package-sha256.txt').read_text().splitlines():
 digest,name=line.split();assert sha((lab/'vm-package-01/packages'/Path(name).name).read_bytes())==digest
result=dict(result='pass',unchanged_sdk_compile_inputs=len(old['compile_inputs']),unchanged_fixtures=len(old['fixtures']),source_package_inputs=manifest,runtime_inputs=checked,
 package_input_sha256=sha((lab/'package-input-03.tar').read_bytes()),prior_sdk_evidence='distribution/evidence/native-transition/root-reinspection-sdk-01',
 current_worker_sha256='b55000d2e21d96c8e75a9f36dda4bbcf5c77c9dbf42074fa39b1600b1c113322')
(lab/'artifact-check.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS',len(manifest),'source package inputs;',len(checked),'runtime files;',len(old['compile_inputs']),'unchanged SDK inputs')
