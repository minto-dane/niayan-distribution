# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import hashlib, json, re, shutil, subprocess, tarfile
lab=Path('/evidence'); workspace=Path('/workspace'); root=workspace
worker=workspace/'build/root-extract'
libs={}
for binary in [worker]:
 for line in subprocess.check_output(['ldd',str(binary)],text=True).splitlines():
  match=re.search(r'(/[^ ]+)',line)
  if match:
   p=Path(match.group(1));assert p.is_file() and p.stat().st_size<64*1024*1024
   if p.name in libs: assert libs[p.name]==p
   libs[p.name]=p
with tarfile.open(lab/'runtime.tar','w') as out:
 for name in ['build','lib','native','native/worker','fixtures']:
  entry=tarfile.TarInfo(name);entry.type=tarfile.DIRTYPE;entry.mode=0o755;entry.uid=entry.gid=0
  out.addfile(entry)
 out.add(worker,arcname='build/root-extract')
 for name,p in sorted(libs.items()): out.add(p.resolve(),arcname='lib/'+name)
 for name in ['root_bank.py','worker/check_root_reinspection.py','worker/check_root_extract.py','worker/check_root_bank.py']:
  p=workspace/'native'/name;out.add(p,arcname='native/'+name)
(lab/'runtime-inputs.json').write_text(json.dumps({'worker':hashlib.sha256(worker.read_bytes()).hexdigest(),
 'libraries':{n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sorted(libs.items())}},indent=2)+'\n')
