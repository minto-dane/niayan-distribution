# SPDX-License-Identifier: MIT
import hashlib,json,re
from pathlib import Path
root=Path('/home/nia/devbox/niaos/nia-os-consent'); target=Path('/home/nia/devbox/niaos/.work/native-generation-retention-01/proof-input-comparison.json')
p=root/'assurance/evidence/native-development/current-component-proof/report.json'; baseline=json.loads(p.read_text());rows=[]
for row in baseline['components']:
 repo=row['repository']; inputs=row['proof_inputs']; changed=[name for name,h in inputs.items() if not (root/repo/name).is_file() or hashlib.sha256((root/repo/name).read_bytes()).hexdigest()!=h]
 gpr=(root/repo/'proof.gpr').read_text();dirs=re.findall(r'"([^"]+)"',re.search(r'for Source_Dirs use\s*\((.*?)\)',gpr,re.S).group(1))
 actual={str(f.relative_to(root/repo)) for d in dirs for f in (root/repo/d).iterdir() if f.suffix in ('.ads','.adb')};expected={n for n in inputs if Path(n).suffix in ('.ads','.adb')}
 rows.append(dict(repository=repo,source_directories=dirs,input_count=len(inputs),changed_inputs=changed,added_sources=sorted(actual-expected),removed_sources=sorted(expected-actual),unchanged=not changed and actual==expected))
assert len(rows)==7 and all(r['unchanged'] for r in rows)
target.write_text(json.dumps(dict(result='unchanged',scope='Exact existing proof input sets only; versioned generation and retention runtime is outside SPARK',baseline=str(p.relative_to(root)),baseline_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),components=rows),indent=2)+'\n')
print('Seven proof input sets unchanged')
