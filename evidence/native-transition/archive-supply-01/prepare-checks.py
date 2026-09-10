# SPDX-License-Identifier: MIT
import hashlib, json, shutil
from pathlib import Path

root=Path('/home/nia/devbox/niaos/nia-os-consent');work=root.parent/'.work/native-archive-supply-01'
excluded={'.git','build','evidence','__pycache__'}
inputs={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob('*') if p.is_file() and not set(p.relative_to(root).parts)&excluded}
support=json.loads((root.parent/'.work/native-publication-intent-01/workspace-supporting-docs.json').read_text())
tree=work/'workspace';tree.mkdir()
for relative,expected in {**inputs,**support}.items():
    source=root/relative;assert not source.is_symlink() and source.stat().st_size<=8*1024*1024
    assert hashlib.sha256(source.read_bytes()).hexdigest()==expected
    target=tree/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
(work/'workspace-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
(work/'workspace-supporting-docs.json').write_text(json.dumps(support,indent=2)+'\n')
print('Copied',len(inputs),'bounded inputs into a fresh qualification workspace')
