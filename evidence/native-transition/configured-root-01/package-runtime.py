# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import hashlib, json, tarfile
root=Path('/home/nia/devbox/niaos/nia-os-consent')
lab=Path(__file__).resolve().parent
prior=lab.parent/'native-root-clocks-01'
report=json.loads((root/'distribution/evidence/native-transition/root-clocks-01/report.json').read_text())
worker=lab/'workspace/build/root-extract'
with tarfile.open(lab/'runtime.tar','w') as out:
 out.add(worker,arcname='build/root-extract')
 for p in sorted((prior/'workspace/lib').iterdir()):
  assert p.is_file() and p.stat().st_size<64*1024*1024
  out.add(p,arcname='lib/'+p.name)
 out.add(root/'distribution/native/worker/check_configured_root.py',arcname='check_configured_root.py')
 for p in sorted((lab/'export-02').iterdir()):
  if p.name != 'report.json' and not p.name.endswith('.tar'): continue
  assert p.is_file() and p.stat().st_size<1024*1024
  out.add(p,arcname='inputs/'+p.name)
print('Packaged unchanged accepted worker and independently verified native root archives')
