# SPDX-License-Identifier: MIT
"""Retain bounded, immutable qualification and actual publication fault evidence."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

root=Path('/home/nia/devbox/niaos/nia-os-consent');work=Path(__file__).resolve().parent
out=root/'distribution/evidence/native-transition/publication-supply-01'
assert not out.exists()
qualification=json.loads((work/'qualification.json').read_text());assert qualification['result']=='pass'
subject=qualification['source_subject'];sys.path.insert(0,str(root/'assurance/ci'));import engineering
assert engineering.source_subject(root)==subject
out.mkdir()
def sha(p):
    assert p.is_file() and not p.is_symlink() and p.stat().st_size<=16*1024*1024,p
    return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(source,name):
    sha(source);target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
def write(name,value): (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
inputs=json.loads((work/'workspace-inputs.json').read_text())
for name,expected in inputs.items(): assert sha(root/name)==sha(work/'workspace'/name)==expected,name
for name in ['qualification.json','workspace-inputs.json','workspace-supporting-docs.json','input-comparison.json',
             'reproducibility.json','elf.json','proof-input-comparison.json','prepare.py','qualify.py','compare.py',
             'run-container.py','run-chaos-container.py','dev-image.id','run-sanitized.py','finish.py','finish-attempt-01.py','finish-run.log','finish-retry-run.log','audit-chaos.py','audit-chaos-attempt-01.py','retain.py']:
    copy(work/name,name)
for check in qualification['checks']:
    log=work/(check['name']+'.log');assert sha(log)==check['log_sha256'];copy(log,log.name)
for label,log,base,count in [('standard','workspace-check.log',work/'workspace',120),('host-source','host-source-check.log',root,24)]:
    line=next(l for l in (work/log).read_text().splitlines() if l.endswith('/report.json'))
    path=base/line.split('/workspace/',1)[1] if label=='standard' else Path(line)
    report=json.loads(path.read_text());assert report['source_subject_before']==report['source_subject_after']==subject
    assert len(report['checks'])==count and all(c['result']=='pass' for c in report['checks'])
    for check in report['checks']:
        if 'log_sha256' in check: assert sha(path.parent/(check['name']+'.log'))==check['log_sha256']
    for source in path.parent.iterdir():copy(source,Path(label)/source.name)
diag=work.parent/'native-publication-supply-01'
for number,folder in [(1,'workspace'),(2,'diagnostic-02'),(3,'diagnostic-03')]:
    label='diagnostic-%02d'%number;mapping=json.loads((diag/(label+'-inputs.json')).read_text());changed=[]
    for name,expected in mapping.items():
        source=diag/folder/'pkgcore'/name;assert sha(source)==expected
        if inputs.get('pkgcore/'+name)!=expected:
            changed.append(name);copy(source,Path(label)/'differing-inputs/pkgcore'/name)
    copy(diag/(label+'-inputs.json'),Path(label)/'inputs.json')
    for source in diag.glob(label+'-*.log'):copy(source,Path(label)/source.name)
    for suffix in ['-oracle.json','-fixed-oracle.json','-fixed-oracle.py']:
        source=diag/(label+suffix)
        if source.exists():copy(source,Path(label)/source.name)
    command=diag/('run-diagnostic.sh' if number==1 else 'run-'+label+'.sh');copy(command,Path(label)/command.name)
    write(label+'/input-differences.json',dict(different_from_final_pkgcore=changed,
        scope='diagnostic source only; later qualification is separate'))
reports=[];chaos=work/'chaos'
for name in ['campaign.py','injection-tools.json','injection-tools-version.log','audit.json','audit.log','audit-attempt-01.log']:
    copy(chaos/name,Path('chaos')/name)
for directory in sorted(chaos.glob('attempt-*')):
    if not directory.is_dir():continue
    copy(chaos/(directory.name+'.log'),Path('chaos')/(directory.name+'.log'))
    for source in directory.rglob('*'):
        if source.is_file():copy(source,Path('chaos')/source.relative_to(chaos))
    report=json.loads((directory/'report.json').read_text())
    if report['result']=='pass':
        execution=json.loads((directory/'execution.json').read_text());assert execution['source_subject']==subject
        reports.append((directory.name,report))
assert len(reports)==2 and {r['seed'] for _,r in reports}=={20260910,20260911}
assert json.loads((chaos/'audit.json').read_text())['result']=='pass'
durations=sorted(c['recovery_ms'] for _,r in reports for c in r['cases'])
counts={kind:sum(r['counts'][kind] for _,r in reports) for kind in reports[0][1]['counts']}
write('chaos/summary.json',dict(result='pass-for-private-publication-lab',source_subject=subject,
    completed_campaigns=[name for name,_ in reports],seeds=[r['seed'] for _,r in reports],case_count=len(durations),counts=counts,
    observed_false_successes=0,recovery_ms=dict(p50=durations[(len(durations)-1)//2],p95=durations[int((len(durations)-1)*.95)],max=max(durations)),
    scope='actual admitted/accepted native publication state and WAL; synthetic stage effects and test authorities; no physical power loss or real root/boot',
    lab_capabilities=['SYS_PTRACE','DAC_READ_SEARCH'],native_runtime_hardening_changed=False,explicit_lab_restore_is_not_product_automatic_repair=True))
print('Retained source-bound v4 qualification and',len(durations),'completed publication fault cases')
