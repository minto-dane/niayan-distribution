# SPDX-License-Identifier: MIT
import hashlib
import json
import os
from pathlib import Path
import shutil

root=Path('/home/nia/devbox/niaos/nia-os-consent');work=Path(__file__).resolve().parent
excluded={'.git','build','evidence','__pycache__','.pytest_cache'}
inputs={}
for parent,dirs,files in os.walk(root,followlinks=False):
    dirs[:]=sorted(d for d in dirs if d not in excluded)
    for name in sorted(files):
        if name in excluded or name.endswith('.pyc'):continue
        source=Path(parent)/name
        assert not source.is_symlink() and source.stat().st_size<=8*1024*1024,source
        inputs[str(source.relative_to(root))]=hashlib.sha256(source.read_bytes()).hexdigest()
support=json.loads((root.parent/'.work/native-supply-revalidation-01/workspace-supporting-docs.json').read_text())
for name in ['workspace','independent-long-path','sanitized']:
    tree=work/name;tree.mkdir()
    for relative,expected in {**inputs,**support}.items():
        if name=='sanitized' and not relative.startswith(('pkgcore/','distribution/')):continue
        source=root/relative
        assert hashlib.sha256(source.read_bytes()).hexdigest()==expected
        target=tree/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        if name=='independent-long-path':os.utime(target,(1788652800,1788652800))
(work/'workspace-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
(work/'workspace-supporting-docs.json').write_text(json.dumps(support,indent=2)+'\n')
print('Prepared',len(inputs),'bounded inputs in fresh qualification trees')
