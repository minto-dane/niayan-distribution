# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import hashlib,io,json,stat,subprocess,tarfile
root=Path('/home/nia/devbox/niaos/nia-os-consent');lab=Path(__file__).resolve().parent
sha=lambda raw:hashlib.sha256(raw).hexdigest()
manifest=json.loads((lab/'package-source-03/source-inputs.json').read_text())['files']
with tarfile.open(lab/'vm-package-07/packages/niaos-root-preparation_0.6.0.tar.xz') as t:
 members={m.name:m for m in t.getmembers() if m.isfile()}
 for relative,item in manifest.items():
  raw=(root/'distribution'/item['source']).read_bytes();assert sha(raw)==item['sha256'],relative
  selected=[m for name,m in members.items() if name.endswith('/'+relative)];assert len(selected)==1
  assert t.extractfile(selected[0]).read()==raw and stat.S_IMODE(selected[0].mode)==item['mode']
main=lab/'vm-package-07/packages/niaos-root-preparation_0.6.0_amd64.deb'
with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['dpkg-deb','--fsys-tarfile',str(main)]))) as t:
 delivered={m.name.removeprefix('./'):t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
 for name in ('root_bank.py','root_freeze.py','bank_device.py','storage_bootstrap.py','root_session.py','root_session_worker.py'):
  assert delivered['usr/libexec/niaos/'+name]==(root/'distribution/native'/name).read_bytes(),name
 for name in ('niaos-root-preparation.service','niaos-root-bank-check.service','niaos-root-session.service','niaos-root-session.socket','niaos-root-session-seal.service'):
  assert delivered['usr/lib/systemd/system/'+name]==(root/'distribution/packaging/root-preparation/debian'/name).read_bytes(),name
 assert delivered['usr/lib/systemd/system/var-lib-niaos-roots.mount']==(root/'distribution/packaging/root-preparation/deployment/var-lib-niaos-roots.mount').read_bytes()
 assert sha(delivered['usr/libexec/niaos/root-extract'])=='b55000d2e21d96c8e75a9f36dda4bbcf5c77c9dbf42074fa39b1600b1c113322'
runtime={}
with tarfile.open(lab/'runtime-07.tar') as t:
 for m in t.getmembers():
  if not m.isfile():continue
  raw=t.extractfile(m).read();runtime[m.name]=sha(raw)
  if m.name.startswith('source/'):assert raw==(lab/'package-source-03'/m.name.removeprefix('source/')).read_bytes(),m.name
  elif m.name in ('check_bank_device.py','check_root_session.py','check_root_extract.py','check_root_reinspection.py'):assert raw==(root/'distribution/native/worker'/m.name).read_bytes()
  elif m.name=='component.deb':
   original=lab.parent/'native-storage-bootstrap-01/niaos-pkgcore_0.1.0+gita3640276f48d_amd64.deb';assert raw==original.read_bytes()
  elif m.name.startswith('dependencies/'):assert raw==(lab.parent/'native-storage-bootstrap-01'/m.name).read_bytes()
  else:raise AssertionError(m.name)
# The actual initializer was reused from a previously accepted component build.
with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['dpkg-deb','--fsys-tarfile',str(original)]))) as t:
 m=next(m for m in t.getmembers() if m.name.endswith('/usr/libexec/nia/pkg_store_bootstrap'))
 initializer_hash=sha(t.extractfile(m).read());assert initializer_hash=='1a163c364f589b77f1fc30bc6a4a5f44232c631c9d70b4152ffd4847cf154300'
app='app/pkg_store_bootstrap.adb'
assert subprocess.check_output(['git','show','a3640276f48d:'+app],cwd=root/'pkgcore')==(root/'pkgcore'/app).read_bytes()
assert not subprocess.check_output(['git','diff','a3640276f48d','--','vendor'],cwd=root/'pkgcore')
packages={}
for line in (lab/'vm-package-07/package-sha256.txt').read_text().splitlines():
 digest,name=line.split();p=lab/'vm-package-07/packages'/Path(name).name;assert sha(p.read_bytes())==digest;packages[p.name]=digest
report=dict(result='pass',source_package_inputs=manifest,runtime_inputs=runtime,packages=packages,delivered_modules_and_units_match=True,
 worker_unchanged=True,initializer_sha256=initializer_hash,initializer_app_and_vendor_unchanged_since='a3640276f48d',
 reused_component_version='0.1.0+gita3640276f48d',all_component_binaries_rebuilt=False,runtime_archive_sha256=sha((lab/'runtime-07.tar').read_bytes()))
with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['dpkg-deb','--fsys-tarfile',str(lab/'vm-package-02/packages/niaos-root-preparation_0.6.0_amd64.deb')]))) as t:
 old={m.name.removeprefix('./'):t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
 stable=[name for name in delivered if name.startswith('usr/libexec/niaos/')]
 for name in stable:assert old[name]==delivered[name],name
for name in ('check_bank_device.py','check_root_session.py','check_root_extract.py','check_root_reinspection.py'):
 with tarfile.open(lab/'runtime-03.tar') as t:assert t.extractfile(name).read()==(root/'distribution/native/worker'/name).read_bytes(),name
report['runtime_modules_and_worker_identical_to_normal_disconnect_expiry_acceptance']=stable
report['unit_delta_since_those_runs']='Independent OnFailure seal service added; final build accepted by VM 07 kill case.'
(lab/'artifact-check.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(manifest),'export inputs;',len(runtime),'runtime files; delivered modules/units/worker/initializer')
