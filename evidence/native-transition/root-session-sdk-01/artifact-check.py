# SPDX-License-Identifier: BSD-3-Clause
import hashlib,io,json,subprocess,tarfile
from pathlib import Path
root=Path('/home/nia/devbox/niaos/nia-os-consent');lab=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
entries=json.loads((lab/'export.json').read_text());compile_inputs=[];other_differences=[]
for entry in entries:
 source=root/entry['path'];exported=lab/'workspace'/entry['path']
 assert sha(exported)==entry['sha256'],entry['path']
 if source.suffix in ('.ads','.adb','.c','.h','.gpr'):
  assert sha(source)==entry['sha256'],entry['path'];compile_inputs.append(entry)
 elif sha(source)!=entry['sha256']:other_differences.append(entry['path'])
assert other_differences==['pkgcore/ci/test-all.sh'],other_differences
assert sha(root/'pkgcore/tests/check_root_session_transport.py')==sha(lab/'workspace/pkgcore/tests/check_root_session_transport.py')
inputs=json.loads((lab/'runtime-inputs.json').read_text())
with tarfile.open(lab/'runtime.tar') as archive:
 for entry in inputs:assert hashlib.sha256(archive.extractfile(entry['path']).read()).hexdigest()==entry['sha256']
 for name,path in [('check_root_session_sdk.py',root/'distribution/native/worker/check_root_session_sdk.py'),('check_root_session_transport.py',root/'pkgcore/tests/check_root_session_transport.py')]:
  assert hashlib.sha256(archive.extractfile(name).read()).hexdigest()==sha(path)
 service=archive.extractfile('service.deb').read()
assert hashlib.sha256(service).hexdigest()=='1da636f597df849c971868984d3dfea813ca3fa1bf838a09bab4ac35e2a43820'
package=root.parent/'.work/native-root-session-01/vm-package-07/packages/niaos-root-preparation_0.6.0_amd64.deb'
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
  if target is not None:
   assert archive.extractfile(member).read()==target.read_bytes(),name;checked.append(name)
vm=json.loads((lab/'vm-test-01/result.json').read_text());assert vm['result']=='pass' and vm['native_library_sha256']==sha(lab/'root-session.so')
assert json.loads((lab/'vm-test-01/exit.json').read_text())['qemu_exit']==0
ada=lab/'workspace/pkgcore/build/test-bin/run_root_session_tests'
assert sha(ada)==json.loads((lab/'reproducibility.json').read_text())['ada_main_sha256']
(lab/'compile-inputs.json').write_text(json.dumps(compile_inputs,indent=2)+'\n')
(lab/'artifact-check.json').write_text(json.dumps(dict(result='pass',compile_inputs=len(compile_inputs),noncompile_changes_after_export=other_differences,controller_package_sha256=sha(package),unchanged_package_files=checked,native_transport_library_sha256=sha(lab/'root-session.so'),ada_main_sha256=sha(ada),runtime_files=len(inputs)),indent=2)+'\n')
print('PASS artifacts',len(compile_inputs),'compile inputs,',len(checked),'unchanged controller files')
