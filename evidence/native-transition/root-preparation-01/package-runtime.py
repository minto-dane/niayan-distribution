from pathlib import Path
import shutil,subprocess,tarfile
root=Path('/workspace');lib=root/'lib';lib.mkdir(exist_ok=True)
for binary in [root/'root-extract',root/'pkgcore/build/test-bin/run_root_archive_tests']:
 for line in subprocess.check_output(['ldd',str(binary)],text=True).splitlines():
  for name in [x for x in line.split() if x.startswith('/')]:
   p=Path(name);assert p.stat().st_size<64*1024**2;shutil.copy2(p,lib/p.name)
with tarfile.open('/evidence/runtime.tar','w') as t:
 for rel in ['root-extract','root_bank.py','check_root_preparation.py','lib','pkgcore/build/test-bin/run_root_archive_tests','pkgcore/tests/fixtures/root-preparation']:
  t.add(root/rel,arcname=rel)
