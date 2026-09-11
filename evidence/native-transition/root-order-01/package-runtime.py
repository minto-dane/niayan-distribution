# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import hashlib, json, tarfile
root=Path('/home/nia/devbox/niaos/nia-os-consent')
lab=Path(__file__).resolve().parent
prior=lab.parent/'native-root-clocks-01'
report=json.loads((root/'distribution/evidence/native-transition/root-clocks-01/report.json').read_text())
worker=prior/'workspace/build/root-extract'
assert hashlib.sha256(worker.read_bytes()).hexdigest()==report['artifacts']['workspace/build/root-extract']
with tarfile.open(lab/'runtime.tar','w') as out:
 out.add(worker,arcname='build/root-extract')
 for p in sorted((prior/'workspace/lib').iterdir()):
  assert p.is_file() and p.stat().st_size<64*1024*1024
  out.add(p,arcname='lib/'+p.name)
 out.add(root/'distribution/native/worker/check_root_order.py',arcname='check_root_order.py')
 for p in sorted((lab/'export-04').iterdir()):
  assert p.is_file() and p.stat().st_size<1024*1024
  out.add(p,arcname='inputs/'+p.name)
print('Packaged unchanged accepted worker and independently verified native root archives')
