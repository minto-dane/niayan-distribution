# SPDX-License-Identifier: MIT
import hashlib,json,subprocess
from pathlib import Path
root=Path('/home/nia/devbox/niaos/nia-os-consent');work=root.parent/'.work/native-archive-supply-01'
excluded={'.git','build','evidence','__pycache__'}
expected=json.loads((work/'workspace-inputs.json').read_text());copies=[]
for tree in [root,work/'workspace']:
    actual={str(p.relative_to(tree)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in tree.rglob('*') if p.is_file() and not set(p.relative_to(tree).parts)&excluded}
    assert actual==expected,tree
    copies.append({'path':str(tree),'inputs':len(actual),'matches':True})
baseline=root/'distribution/evidence/native-transition/publication-intent-01'
previous=json.loads((baseline/'workspace-inputs.json').read_text())
for row in json.loads((baseline/'handoff-only-changes.json').read_text())['changes']:
    assert previous[row['path']]==row['before_sha256'];previous[row['path']]=row['after_sha256']
added=sorted(set(expected)-set(previous));removed=sorted(set(previous)-set(expected))
changed=sorted(k for k in set(previous)&set(expected) if previous[k]!=expected[k])
assert not removed
assert all(p.startswith(('distribution/','assurance/engineering/','assurance/docs/')) for p in added+changed)
repositories=['assurance','pkgcore','statecore','controlcore','configcore','resolvercore','capsulecore']
unchanged=[]
for repo in repositories:
    code={p:h for p,h in expected.items() if p.startswith(repo+'/') and Path(p).parts[1] not in ('docs','engineering')}
    old={p:h for p,h in previous.items() if p.startswith(repo+'/') and Path(p).parts[1] not in ('docs','engineering')}
    assert code==old
    unchanged.append({'repository':repo,'inputs':len(code),'unchanged':True})
report={'result':'pass','baseline_root_commit':'c015455','baseline_subject':json.loads((baseline/'report.json').read_text())['source_subject'],
        'copies':copies,'added':added,'removed':removed,'changed':changed,'unchanged_component_inputs':unchanged,
        'ada_build_repeated':False,'proof_repeated':False,'scope':'Every component input outside docs/engineering unchanged; Python supply and test environment changes qualified separately'}
(work/'input-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
print('Exact current copies match;',len(changed),'changed and',len(added),'added paths; seven component code/build/test input sets unchanged')
