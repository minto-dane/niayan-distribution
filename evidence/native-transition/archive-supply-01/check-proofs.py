# SPDX-License-Identifier: MIT
import hashlib,json,re
from pathlib import Path
root=Path('/home/nia/devbox/niaos/nia-os-consent');work=root.parent/'.work/native-archive-supply-01'
source=root/'assurance/evidence/native-development/current-component-proof/report.json'
baseline=json.loads(source.read_text());rows=[]
for row in baseline['components']:
    repo=row['repository'];inputs=row['proof_inputs']
    changed=[name for name,h in inputs.items() if not (root/repo/name).is_file() or hashlib.sha256((root/repo/name).read_bytes()).hexdigest()!=h]
    gpr=(root/repo/'proof.gpr').read_text()
    dirs=re.findall(r'"([^"]+)"',re.search(r'for Source_Dirs use\s*\((.*?)\)',gpr,re.S).group(1))
    actual={str(p.relative_to(root/repo)) for d in dirs for p in (root/repo/d).iterdir() if p.suffix in ('.ads','.adb')}
    expected={p for p in inputs if Path(p).suffix in ('.ads','.adb')}
    assert not changed and actual==expected
    rows.append({'repository':repo,'input_count':len(inputs),'changed_inputs':changed,'added_sources':[],'removed_sources':[],'unchanged':True})
assert len(rows)==7
(work/'proof-input-comparison.json').write_text(json.dumps({'result':'unchanged','baseline':str(source.relative_to(root)),
    'baseline_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'components':rows,
    'scope':'Exact mathematical input sets unchanged; Python supply changes are not formal proofs'},indent=2)+'\n')
print('Seven exact proof input sets unchanged; no repeated proof execution')
