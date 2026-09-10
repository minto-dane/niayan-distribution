# SPDX-License-Identifier: MIT
"""Retain exact qualified source, independent builds and bounded map fault runs."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

root=Path('/home/nia/devbox/niaos/nia-os-consent');work=Path(__file__).resolve().parent
destination=root/'distribution/evidence/native-transition/supply-map-01'
destination.mkdir()

def sha(path):
    assert path.is_file() and not path.is_symlink() and path.stat().st_size<=16*1024*1024,path
    return hashlib.sha256(path.read_bytes()).hexdigest()

def copy(source,name):
    sha(source);target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)

def write(name,value):
    (destination/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

qualification=json.loads((work/'qualification.json').read_text());assert qualification['result']=='pass'
subject=qualification['source_subject'];sys.path.insert(0,str(root/'assurance/ci'));import engineering
assert engineering.source_subject(root)==subject
inputs=json.loads((work/'workspace-inputs.json').read_text())
for name,expected in inputs.items():
    assert sha(root/name)==expected and sha(work/'workspace'/name)==expected,name
for name in ('qualification.json','workspace-inputs.json','workspace-supporting-docs.json',
             'input-comparison.json','reproducibility.json','elf.json','proof-input-comparison.json',
             'prepare.py','qualify.py','compare.py','run-container.py','run-chaos-container.py',
             'run-sanitized.py','retain.py','dev-image.id'):
    copy(work/name,name)
for check in qualification['checks']:
    p=work/(check['name']+'.log');assert sha(p)==check['log_sha256'];copy(p,p.name)
for label,log,base,count in [('standard','workspace-check.log',work/'workspace',120),
                           ('host-source','host-source-check.log',root,24)]:
    line=next(l for l in (work/log).read_text().splitlines() if l.endswith('/report.json'))
    path=base/line.split('/workspace/',1)[1] if label=='standard' else Path(line)
    report=json.loads(path.read_text())
    assert report['source_subject_before']==report['source_subject_after']==subject
    assert len(report['checks'])==count and all(c['result']=='pass' for c in report['checks'])
    for check in report['checks']:
        if 'log_sha256' in check:assert sha(path.parent/(check['name']+'.log'))==check['log_sha256']
    for source in path.parent.iterdir():copy(source,Path(label)/source.name)

prior=work.parent/'native-supply-map-01'
mapping=json.loads((prior/'diagnostic-01-inputs.json').read_text());changed=[]
for name,expected in mapping.items():
    source=prior/'diagnostic-01/pkgcore'/name;assert sha(source)==expected
    if inputs.get('pkgcore/'+name)!=expected:
        copy(source,Path('diagnostic-01/differing-inputs/pkgcore')/name);changed.append(name)
for name in ('diagnostic-01-inputs.json','diagnostic-01-source-inputs.json','diagnostic-01-build.log','diagnostic-01-tests.log'):
    copy(prior/name,Path('diagnostic-01')/name)
write('diagnostic-01/input-differences.json',{'different_from_final_pkgcore':changed,
      'result':'preliminary driver passed 712 assertions; final driver and integration were separately qualified'})
for label,base,mapping_name,folder,log in [
    ('boundary-failure',prior,'boundary-01-inputs.json','boundary-01/pkgcore','boundary-01.log'),
    ('boundary-fixed',work,'boundary-fixed-inputs.json','boundary-fixed/pkgcore','boundary-fixed.log')]:
    mapping=json.loads((base/mapping_name).read_text());changed=[]
    for name,expected in mapping.items():
        source=base/folder/name;assert sha(source)==expected
        if inputs.get('pkgcore/'+name)!=expected:
            copy(source,Path(label)/'differing-inputs/pkgcore'/name);changed.append(name)
    copy(base/mapping_name,Path(label)/'inputs.json');copy(base/log,Path(label)/'run.log')
    write(label+'/input-differences.json',{'different_from_final_pkgcore':changed})
# Prior complete gates passed before the additional valid-index regression.
# Preserve that evidence without counting it as final qualification.
old=json.loads((prior/'qualification.json').read_text());assert old['result']=='pass'
for name in ('qualification.json','workspace-inputs.json','input-comparison.json','reproducibility.json',
             'elf.json','proof-input-comparison.json','qualify.py','compare.py'):
    copy(prior/name,Path('before-boundary-regression')/name)
for check in old['checks']:
    p=prior/(check['name']+'.log');assert sha(p)==check['log_sha256']
    copy(p,Path('before-boundary-regression')/p.name)
for label,log,base,count in [('standard','workspace-check.log',prior/'workspace',120),
                           ('host-source','host-source-check.log',root,24)]:
    line=next(l for l in (prior/log).read_text().splitlines() if l.endswith('/report.json'))
    path=base/line.split('/workspace/',1)[1] if label=='standard' else Path(line)
    r=json.loads(path.read_text());assert r['source_subject_before']==r['source_subject_after']==old['source_subject']
    assert len(r['checks'])==count and all(c['result']=='pass' for c in r['checks'])
    for check in r['checks']:
        if 'log_sha256' in check:assert sha(path.parent/(check['name']+'.log'))==check['log_sha256']
    for p in path.parent.iterdir():copy(p,Path('before-boundary-regression')/label/p.name)
old_inputs=json.loads((prior/'workspace-inputs.json').read_text());changed=[]
for name,expected in old_inputs.items():
    source=prior/'workspace'/name;assert sha(source)==expected
    if inputs.get(name)!=expected:
        copy(source,Path('before-boundary-regression/differing-inputs')/name);changed.append(name)
write('before-boundary-regression/input-differences.json',{'different_from_final_inputs':changed,
      'scope':'Prior complete gates are not final regression qualification'})
chaos=work/'chaos'
for name in ('campaign.py','map_chaos_driver.adb','chaos.gpr','build.log','injection-tools.json','injection-tools-version.log'):
    copy(chaos/name,Path('chaos')/name)
reports=[]
for directory in sorted(chaos.glob('attempt-*')):
    if not directory.is_dir():continue
    copy(chaos/(directory.name+'.log'),Path('chaos')/(directory.name+'.log'))
    for source in directory.rglob('*'):
        if source.is_file():copy(source,Path('chaos')/source.relative_to(chaos))
    report=json.loads((directory/'report.json').read_text())
    if report['result']=='pass':
        assert report['case_count'] in (34,36)
        reports.append((directory.name,report))
assert len(reports)==2
durations=sorted(c['recovery_ms'] for _,r in reports for c in r['cases'])
counts={kind:sum(r['counts'][kind] for _,r in reports) for kind in reports[0][1]['counts']}
write('chaos/summary.json',{'result':'pass-for-scoped-lab-only','source_subject':subject,
      'completed_campaigns':[name for name,_ in reports],'seeds':[r['seed'] for _,r in reports],
      'case_count':len(durations),'counts':counts,'observed_false_successes':0,
      'recovery_ms':{'p50':durations[(len(durations)-1)//2],
                     'p95':durations[int((len(durations)-1)*.95)],'max':max(durations)},
      'native_runtime_hardening_changed':False,'lab_capabilities':['SYS_PTRACE','DAC_READ_SEARCH'],
      'scope':'candidate supply map only; no accepted publication, physical power loss or boot',
      'quarantine_and_restore_are_explicit_lab_actions':True})
print('Retained source-bound standard qualification and',len(durations),'completed map chaos cases')
