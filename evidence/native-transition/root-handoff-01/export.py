# SPDX-License-Identifier: BSD-3-Clause
import hashlib,json,subprocess
from pathlib import Path
root=Path('/home/nia/devbox/niaos/nia-os-consent');lab=Path(__file__).resolve().parent
out=lab/'workspace';out.mkdir(exist_ok=True)
entries=[]
for repo in ('pkgcore',):
 paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=root/repo,text=True).splitlines()
 for name in sorted(set(paths)):
  source=root/repo/name
  if not source.is_file():continue
  target=out/repo/name;target.parent.mkdir(parents=True,exist_ok=True)
  raw=source.read_bytes();target.write_bytes(raw);target.chmod(source.stat().st_mode&0o777)
  entries.append({'path':repo+'/'+name,'sha256':hashlib.sha256(raw).hexdigest()})
(lab/'export.json').write_text(json.dumps(entries,indent=2)+'\n')
