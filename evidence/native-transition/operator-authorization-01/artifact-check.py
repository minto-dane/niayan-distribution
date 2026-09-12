# SPDX-License-Identifier: BSD-3-Clause
import hashlib,io,json,subprocess,tarfile
from pathlib import Path
root=Path('/home/nia/devbox/niaos/nia-os-consent');lab=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
entries=json.loads((lab/'export.json').read_text());compile_inputs=[];differences=[]
for entry in entries:
 source=root/entry['path'];exported=lab/'workspace'/entry['path']
 assert sha(exported)==entry['sha256'],entry['path']
 if source.suffix in ('.ads','.adb','.c','.h','.gpr'):
  assert sha(source)==entry['sha256'],entry['path'];compile_inputs.append(entry)
 elif sha(source)!=entry['sha256']:differences.append(entry['path'])
assert sorted(differences)==['pkgcore/ci/test-all.sh','pkgcore/packaging/rpm/mission-pkgcore.spec'],differences
for name in ['tests/check_operator_transport.py','tests/helpers/operator_authority_fixture.c']:
 assert sha(root/'pkgcore'/name)==sha(lab/'workspace/pkgcore'/name)
inputs=json.loads((lab/'runtime-inputs.json').read_text())
package_inputs=json.loads((lab/'package-source/source-inputs.json').read_text())['files']
with tarfile.open(lab/'runtime.tar') as archive:
 for entry in inputs:assert hashlib.sha256(archive.extractfile(entry['path']).read()).hexdigest()==entry['sha256']
 for name,entry in package_inputs.items():
  raw=(root/'distribution'/entry['source']).read_bytes()
  assert hashlib.sha256(raw).hexdigest()==entry['sha256'],name
  assert raw==(lab/'package-source'/name).read_bytes()==archive.extractfile('source/'+name).read(),name
 assert archive.extractfile('check_operator_authorization.py').read()==(root/'distribution/native/worker/check_operator_authorization.py').read_bytes()
 assert archive.extractfile('operator-ada').read()==(lab/'workspace/pkgcore/build/test-bin/run_operator_authorization_tests').read_bytes()
package=lab/'vm-package-01/packages/niaos-root-preparation_0.7.0_amd64.deb'
raw=subprocess.check_output(['dpkg-deb','--fsys-tarfile',str(package)])
checked=[]
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
 for member in archive.getmembers():
  if not member.isfile():continue
  name=member.name.removeprefix('./');target=None
  if name.startswith('usr/libexec/niaos/') and name.endswith('.py'):target=root/'distribution/native'/Path(name).name
  elif name.startswith('usr/lib/systemd/system/'):
   target=root/'distribution/packaging/root-preparation/debian'/Path(name).name
   if not target.is_file():target=root/'distribution/packaging/root-preparation/deployment'/Path(name).name
  elif name=='usr/share/polkit-1/actions/org.niaos.package.policy':target=root/'distribution/packaging/root-preparation/deployment/org.niaos.package.policy'
  if target is not None:
   assert archive.extractfile(member).read()==target.read_bytes(),name;checked.append(name)
  if name=='usr/libexec/niaos/root-extract':
   assert hashlib.sha256(archive.extractfile(member).read()).hexdigest()=='b55000d2e21d96c8e75a9f36dda4bbcf5c77c9dbf42074fa39b1600b1c113322'
vm=json.loads((lab/'vm-package-01/result.json').read_text());assert vm['result']=='pass' and vm['library_sha256']==sha(lab/'operator-authorization.so')
assert json.loads((lab/'vm-package-01/exit.json').read_text())['qemu_exit']==0
ada=lab/'workspace/pkgcore/build/test-bin/run_operator_authorization_tests'
assert sha(ada)==json.loads((lab/'reproducibility.json').read_text())['ada_main_sha256']
(lab/'compile-inputs.json').write_text(json.dumps(compile_inputs,indent=2)+'\n')
(lab/'artifact-check.json').write_text(json.dumps(dict(result='pass',compile_inputs=len(compile_inputs),noncompile_changes_after_export=differences,controller_package_sha256=sha(package),package_files_checked=checked,package_export_files=len(package_inputs),native_transport_library_sha256=sha(lab/'operator-authorization.so'),ada_main_sha256=sha(ada),runtime_files=len(inputs),existing_apps_built=6,rpm_build_executed=False),indent=2)+'\n')
print('PASS artifacts',len(compile_inputs),'compile inputs,',len(checked),'package files')
