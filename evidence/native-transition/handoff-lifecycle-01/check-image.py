# SPDX-License-Identifier: BSD-3-Clause
import hashlib,json,subprocess,sys
from pathlib import Path
p=Path('/evidence');root=Path('/workspace')
manifest=json.loads((p/'new-image-check-inputs.json').read_text())
def verify():
 for name,expected in manifest.items():
  assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected,name
verify()
with (p/'image-handoff-check.log').open('w') as log:
 subprocess.run(['make','-C','distribution','handoff-check'],cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
with (p/'image-c-proof.log').open('w') as log:
 subprocess.run(['make','c-proof','C_PROOF_OUTPUT=/evidence/image-c-proof'],cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
verify()
packages=subprocess.check_output(['dpkg-query','-W','-f=${Package} ${Version}\n'],text=True)
(p/'image-packages.txt').write_text(packages)
(p/'image-tools-report.json').write_text(json.dumps(dict(result='pass',python=sys.version,inputs=manifest,packages_sha256=hashlib.sha256(packages.encode()).hexdigest(),new_image_build=True,remote_ci=False,full_suite=False,production_qualified=False),indent=2)+'\n')
