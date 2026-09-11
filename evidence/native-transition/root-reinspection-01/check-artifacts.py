# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import hashlib, io, json, subprocess, tarfile
lab=Path(__file__).resolve().parent
root=Path('/home/nia/devbox/niaos/nia-os-consent/distribution')
sha=lambda raw:hashlib.sha256(raw).hexdigest()
source=lab/'package-source-final'
manifest=json.loads((source/'source-inputs.json').read_text())
with tarfile.open(lab/'vm-package-05/packages/niaos-root-preparation_0.3.0.tar.xz','r:xz') as tar:
 members={m.name:m for m in tar if m.isfile()}
 prefix=next(n[:-len('source-inputs.json')] for n in members if n.endswith('/source-inputs.json'))
 assert tar.extractfile(members[prefix+'source-inputs.json']).read()==(source/'source-inputs.json').read_bytes()
 for name,entry in manifest['files'].items():
  raw=(root/entry['source']).read_bytes()
  assert sha(raw)==entry['sha256'] and raw==(source/name).read_bytes()
  assert raw==tar.extractfile(members[prefix+name]).read()
with tarfile.open(lab/'package-input-05.tar') as tar:
 tests={}
 for name in ['root_bank.py','worker/check_root_extract.py','worker/check_root_bank.py','worker/check_root_reinspection.py']:
  raw=tar.extractfile('tests/'+name).read()
  assert raw==(root/'native'/name).read_bytes()
  tests['native/'+name]=sha(raw)
files={}
for line in (lab/'vm-package-05/package-sha256.txt').read_text().splitlines():
 digest,name=line.split();path=lab/'vm-package-05/packages'/Path(name).name
 assert path.stat().st_size<1024*1024 and sha(path.read_bytes())==digest
 files[path.name]=digest
raw=subprocess.check_output(['dpkg-deb','--fsys-tarfile',str(lab/'vm-package-05/packages/niaos-root-preparation_0.3.0_amd64.deb')])
with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
 worker=sha(tar.extractfile('./usr/libexec/niaos/root-extract').read())
 assert tar.extractfile('./usr/libexec/niaos/root_bank.py').read()==(root/'native/root_bank.py').read_bytes()
observed=json.loads((lab/'vm-package-05/result.json').read_text())
assert observed['cases']['healthy']['worker_sha256']==worker
assert worker=='b55000d2e21d96c8e75a9f36dda4bbcf5c77c9dbf42074fa39b1600b1c113322'
(lab/'artifact-verification.json').write_text(json.dumps(dict(result='pass',source_export_and_package_match_current_source=True,source_files=len(manifest['files']),tests=tests,packages=files,installed_worker_sha256=worker),indent=2)+'\n')
print('PASS exported source, packaged source, actual ELF, service and VM test inputs')
