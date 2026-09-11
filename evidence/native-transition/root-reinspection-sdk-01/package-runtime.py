# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import hashlib,json,re,subprocess,tarfile
lab=Path('/evidence'); workspace=Path('/workspace');root=workspace/'pkgcore'
libs={};drivers={name:root/'build/test-bin'/name for name in ['run_root_configuration_tests','run_root_archive_tests']}
for driver in drivers.values():
 for line in subprocess.check_output(['ldd',str(driver)],text=True).splitlines():
  match=re.search(r'(/[^ ]+)',line)
  if match:
   p=Path(match.group(1));assert p.is_file() and p.stat().st_size<64*1024*1024
   if p.name in libs: assert libs[p.name]==p
   libs[p.name]=p
with tarfile.open(lab/'runtime.tar','w') as out:
 for name in ['build','lib','native','native/worker','fixtures','fixtures/conffiles','fixtures/root-preparation']:
  entry=tarfile.TarInfo(name);entry.type=tarfile.DIRTYPE;entry.mode=0o755;entry.uid=entry.gid=0;out.addfile(entry)
 for name,p in drivers.items():out.add(p,arcname='build/'+name)
 out.add(lab/'service.deb',arcname='service.deb')
 for name,p in sorted(libs.items()):out.add(p.resolve(),arcname='lib/'+name)
 for name in ['root_bank.py','worker/check_root_preparation.py','worker/check_root_reinspection.py','worker/check_root_extract.py']:
  out.add(workspace/'native'/name,arcname='native/'+name)
 for folder in ['conffiles','root-preparation']:
  for p in sorted((root/'tests/fixtures'/folder).rglob('*')):
   if p.is_file():
    assert p.stat().st_size<1024*1024
    out.add(p,arcname='fixtures/'+folder+'/'+p.relative_to(root/'tests/fixtures'/folder).as_posix())
(lab/'runtime-inputs.json').write_text(json.dumps({'drivers':{n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in drivers.items()},'libraries':{n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sorted(libs.items())},'service_deb':hashlib.sha256((lab/'service.deb').read_bytes()).hexdigest()},indent=2)+'\n')
