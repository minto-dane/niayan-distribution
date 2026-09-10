from pathlib import Path
import subprocess, shutil, tarfile
root=Path('/workspace');lib=root/'lib';lib.mkdir(exist_ok=True)
output=subprocess.check_output(['ldd',str(root/'build/root-extract')],text=True)
print(output)
for line in output.splitlines():
 parts=line.split();paths=[p for p in parts if p.startswith('/')]
 for path in paths:
  p=Path(path);assert p.stat().st_size < 64*1024*1024;shutil.copy2(p,lib/p.name)
with tarfile.open('/evidence/runtime.tar','w') as t:
 for rel in ['build/root-extract','check_root_extract.py','check_root_bank.py','root_bank.py','lib']: t.add(root/rel,arcname=rel)
