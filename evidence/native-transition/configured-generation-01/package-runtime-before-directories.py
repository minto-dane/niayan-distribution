# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import hashlib, json, re, shutil, subprocess, tarfile
lab=Path('/evidence'); workspace=Path('/workspace'); root=workspace/'pkgcore'
driver=root/'build/test-bin/run_root_configuration_tests'; worker=workspace/'build/root-extract'
# Exact private worker previously qualified in configured-root-01/report.json.
# The installed Debian package has a distinct, separately recorded binary hash.
assert hashlib.sha256(worker.read_bytes()).hexdigest()=='ed188c4f23f9078ecaecfff829de6f4a53ba533f0a36a77c6189d5a09a9a123d'
libs={}
for binary in [driver,worker]:
 for line in subprocess.check_output(['ldd',str(binary)],text=True).splitlines():
  match=re.search(r'(/[^ ]+)',line)
  if match:
   p=Path(match.group(1));assert p.is_file() and p.stat().st_size<64*1024*1024
   if p.name in libs: assert libs[p.name]==p
   libs[p.name]=p
with tarfile.open(lab/'runtime.tar','w') as out:
 out.add(worker,arcname='build/root-extract');out.add(driver,arcname='build/driver')
 for name,p in sorted(libs.items()): out.add(p.resolve(),arcname='lib/'+name)
 for name in ['root_bank.py','worker/check_root_preparation.py']:
  p=workspace/'native'/name;out.add(p,arcname='native/'+name)
 for p in sorted((root/'tests/fixtures/conffiles').iterdir()):
  assert p.is_file() and p.stat().st_size<1024*1024
  out.add(p,arcname='fixtures/'+p.name)
(lab/'runtime-inputs.json').write_text(json.dumps({'worker':hashlib.sha256(worker.read_bytes()).hexdigest(),
 'driver':hashlib.sha256(driver.read_bytes()).hexdigest(), 'libraries':{n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sorted(libs.items())}},indent=2)+'\n')
