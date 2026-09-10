# SPDX-License-Identifier: MIT
"""Retain bounded qualification artifacts, including unsuccessful attempts."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

root = Path('/home/nia/devbox/niaos/nia-os-consent')
work = Path(__file__).resolve().parent
destination = root/'distribution/evidence/native-transition/archive-receipt-01'
destination.mkdir()


def sha(path):
    assert path.is_file() and not path.is_symlink() and path.stat().st_size <= 16*1024*1024, path
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, name):
    sha(source)
    target = destination/name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def write(name, value):
    (destination/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


qualification = json.loads((work/'qualification.json').read_text())
assert qualification['result'] == 'pass'
subject = qualification['source_subject']
sys.path.insert(0, str(root/'assurance/ci'))
import engineering
assert engineering.source_subject(root) == subject
assert engineering.source_subject(work/'workspace') == subject
inputs = json.loads((work/'workspace-inputs.json').read_text())
for name, expected in inputs.items():
    assert sha(root/name) == expected and sha(work/'workspace'/name) == expected, name
for name in ('qualification.json', 'workspace-inputs.json', 'workspace-supporting-docs.json',
             'input-comparison.json', 'reproducibility.json', 'elf.json', 'proof-input-comparison.json',
             'prepare.py', 'qualify.py', 'compare.py', 'run-container.py', 'run-chaos-container.py',
             'run-sanitized.py', 'retain.py', 'dev-image.id'):
    copy(work/name, name)
for check in qualification['checks']:
    path = work/(check['name']+'.log')
    assert sha(path) == check['log_sha256']
    copy(path, path.name)

for label, path, count in (
    ('standard', work/'workspace/assurance/evidence/engineering-uoh97vz4/report.json', 118),
    ('host-source', root/'assurance/evidence/engineering-whf8jrya/report.json', 24)):
    report = json.loads(path.read_text())
    assert report['source_subject_before'] == report['source_subject_after'] == subject
    assert len(report['checks']) == count and all(c['result'] == 'pass' for c in report['checks'])
    for check in report['checks']:
        if 'log_sha256' in check:
            assert sha(path.parent/(check['name']+'.log')) == check['log_sha256']
    for source in path.parent.iterdir():
        copy(source, Path(label)/source.name)

for prefix in ('diagnostic-01', 'diagnostic-02'):
    mapping = json.loads((work/(prefix+'-inputs.json')).read_text())
    changed = []
    for name, expected in mapping.items():
        source = work/prefix/'pkgcore'/name
        assert sha(source) == expected
        if inputs.get('pkgcore/'+name) != expected:
            copy(source, Path(prefix)/'differing-inputs/pkgcore'/name)
            changed.append('pkgcore/'+name)
    copy(work/(prefix+'-inputs.json'), Path(prefix)/'pkgcore-inputs.json')
    for path in work.glob(prefix+'-*.log'):
        copy(path, Path(prefix)/path.name)
    if prefix == 'diagnostic-02':
        mapping = json.loads((work/(prefix+'-distribution-inputs.json')).read_text())
        for name, expected in mapping.items():
            source = work/prefix/'distribution'/name
            assert sha(source) == expected
            if inputs.get('distribution/'+name) != expected:
                copy(source, Path(prefix)/'differing-inputs/distribution'/name)
                changed.append('distribution/'+name)
        copy(work/(prefix+'-distribution-inputs.json'), Path(prefix)/'distribution-inputs.json')
    write(prefix+'/input-differences.json', {'different_from_qualified_inputs': changed,
          'image': 'sha256:0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a'})

for path in work.glob('dev-image-*.log'):
    copy(path, Path('image-build')/path.name)
for folder in sorted(work.glob('dev-image-context*')):
    for path in folder.rglob('*'):
        if path.is_file():
            copy(path, Path('image-build')/path.relative_to(work))

chaos = work/'chaos'
for name in ('campaign.py', 'chaos_driver.adb', 'chaos.gpr', 'build.log', 'ptrace-probe.log', 'injection-tools.json'):
    copy(chaos/name, Path('chaos')/name)
reports = []
for number in range(1, 6):
    name = 'attempt-%02d' % number
    copy(chaos/(name+'.log'), Path('chaos')/(name+'.log'))
    for path in (chaos/name).rglob('*'):
        if path.is_file():
            copy(path, Path('chaos')/path.relative_to(chaos))
    report = json.loads((chaos/name/'report.json').read_text())
    if number >= 4:
        assert report['result'] == 'pass' and report['case_count'] == 92
        reports.append(report)
    else:
        assert report['result'] == 'failed'
durations = sorted(c['recovery_ms'] for r in reports for c in r['cases'])
counts = {kind: sum(r['counts'][kind] for r in reports) for kind in reports[0]['counts']}
write('chaos/summary.json', {'result': 'pass-for-scoped-lab-only', 'source_subject': subject,
      'seeds': [r['seed'] for r in reports], 'completed_campaigns': 2, 'case_count': len(durations),
      'counts': counts, 'observed_false_successes': 0,
      'recovery_ms': {'p50': durations[(len(durations)-1)//2],
                      'p95': durations[int((len(durations)-1)*.95)], 'max': max(durations)},
      'prior_attempts': ['insufficient trace visibility', 'missing proc FD path visibility',
                         '81 completed cases, later delay not reached before deadline'],
      'prior_attempts_in_completed_totals': False,
      'lab_capabilities': ['SYS_PTRACE', 'DAC_READ_SEARCH'],
      'runtime_hardening_modified': False, 'network': 'none', 'uid': 1000,
      'quarantine_and_structural_restore_are_explicit_lab_actions': True,
      'crash_recovery_can_leave_unreferenced_incoming_objects': True,
      'physical_power_loss_and_boot_and_full_transactions': 'not qualified'})
print('Retained standard gates, image/diagnostic failures, and 184 completed chaos cases')
