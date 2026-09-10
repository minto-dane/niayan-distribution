# SPDX-License-Identifier: MIT
"""Retain bounded evidence and compare exact current and previous inputs."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

root = Path('/home/nia/devbox/niaos/nia-os-consent')
work = Path(__file__).resolve().parent
destination = root/'distribution/evidence/native-transition/supply-revalidation-01'
destination.mkdir()
def sha(path):
    assert path.is_file() and not path.is_symlink() and path.stat().st_size <= 16*1024*1024
    return hashlib.sha256(path.read_bytes()).hexdigest()
def copy(source, name):
    sha(source)
    target = destination/name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
def write(name, value):
    (destination/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

report = json.loads((work/'report.json').read_text())
assert report['result'] == 'pass'
sys.path.insert(0, str(root/'assurance/ci'))
import engineering
assert engineering.source_subject(root) == report['source_subject']
assert engineering.source_subject(work/'workspace') == report['source_subject']
inputs = json.loads((work/'workspace-inputs.json').read_text())
handoff = []
for name, expected in inputs.items():
    assert sha(work/'workspace'/name) == expected
    current = sha(root/name)
    if current != expected:
        assert name in ('AGENTS.md', 'STATUS.ja.md'), name
        handoff.append({'path': name, 'before_sha256': expected, 'after_sha256': current})
write('handoff-only-changes.json', {'changes': handoff, 'source_subject_changed': False})
previous = json.loads((root/'distribution/evidence/native-transition/archive-supply-01/workspace-inputs.json').read_text())
components = []
for repo in engineering.REPOS:
    def relevant(mapping):
        return {p:h for p,h in mapping.items() if p.startswith(repo+'/') and Path(p).parts[1] not in ('docs', 'engineering')}
    assert relevant(inputs) == relevant(previous), repo
    components.append({'repository': repo, 'inputs': len(relevant(inputs)), 'unchanged': True})
write('component-input-comparison.json', {'baseline_root_commit': '7959751', 'components': components,
      'scope': 'Every component input outside docs and engineering unchanged', 'ada_build_repeated': False})
baseline = root/'assurance/evidence/native-development/current-component-proof/report.json'
proofs = []
for row in json.loads(baseline.read_text())['components']:
    repo = row['repository']
    proof_inputs = row['proof_inputs']
    for name, expected in proof_inputs.items():
        assert sha(root/repo/name) == expected, (repo, name)
    gpr = (root/repo/'proof.gpr').read_text()
    dirs = re.findall(r'"([^"]+)"', re.search(r'for Source_Dirs use\s*\((.*?)\)', gpr, re.S).group(1))
    actual = {str(p.relative_to(root/repo)) for d in dirs for p in (root/repo/d).iterdir() if p.suffix in ('.ads', '.adb')}
    assert actual == {p for p in proof_inputs if Path(p).suffix in ('.ads', '.adb')}
    proofs.append({'repository': repo, 'inputs': len(proof_inputs), 'unchanged': True})
assert len(proofs) == 7
write('proof-input-comparison.json', {'baseline': str(baseline.relative_to(root)), 'baseline_sha256': sha(baseline),
      'components': proofs, 'formal_proof_repeated': False})
for name in ('report.json', 'workspace-inputs.json', 'workspace-supporting-docs.json', 'qualify.py', 'retain.py',
             'native-image-check.log', 'container-source-check.log', 'host-source-check.log', 'engineering-lint.log'):
    copy(work/name, name)
for name, base in [('container', work/'workspace'), ('host', root)]:
    lines = (work/(name+'-source-check.log')).read_text().splitlines()
    line = next(l for l in lines if l.endswith('/report.json'))
    path = base/line.split('/workspace/', 1)[1] if name == 'container' else Path(line)
    source_report = json.loads(path.read_text())
    assert source_report['source_subject_before'] == source_report['source_subject_after'] == report['source_subject']
    assert len(source_report['checks']) == 24 and all(c['result'] == 'pass' for c in source_report['checks'])
    for entry in source_report['checks']:
        if 'log_sha256' in entry:
            assert sha(path.parent/(entry['name']+'.log')) == entry['log_sha256']
    for source in path.parent.iterdir():
        copy(source, Path(name+'-source')/source.name)
print('Retained exact source evidence; seven component and mathematical input sets unchanged')
