# SPDX-License-Identifier: MIT
import hashlib,json,shutil,sys
from pathlib import Path
root=Path('/home/nia/devbox/niaos/nia-os-consent');w=Path(__file__).resolve().parent;b=w.parent/'native-shared-preflight-01'
e=root/'distribution/evidence/native-transition/shared-preflight-01'
q=json.loads((w/'qualification.json').read_text());assert q['result']=='pass'
sys.path.insert(0,str(root/'assurance/ci'));import engineering
assert engineering.source_subject(root)==q['source_subject'];assert not e.exists();e.mkdir()
def sha(p):
 assert p.is_file() and not p.is_symlink() and p.stat().st_size<=16*1024*1024,p
 return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(src,name):
 sha(src);dest=e/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
def write(name,obj):
 p=e/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
inputs=json.loads((w/'workspace-inputs.json').read_text())
for name,digest in inputs.items():assert sha(root/name)==digest and sha(w/'workspace'/name)==digest,name
for name in ['prepare.py','qualify.py','resume-standard.py','resume-qualification.py','finish-resume.py','resume-qualification-run.log','finish-resume.log','reclaim-obsolete-isos.py','reclaim-obsolete-isos-attempt-01.py','capacity-recovery.json','compare.py','run-container.py','dev-image.id','retain.py','prepare.log','qualification.json','qualification-run.log','comparison-run.log','workspace-inputs.json','workspace-supporting-docs.json','input-comparison.json','reproducibility.json','elf.json','proof-input-comparison.json']:
 copy(w/name,name)
for check in q['checks']:
 name=check['name']+'.log';assert sha(w/name)==check['log_sha256'];copy(w/name,name)
initial=w/'workspace/assurance/evidence/engineering-71munqnc'
old=json.loads((initial/'report.json').read_text());assert old['result']=='incomplete-or-failed'
assert old['source_subject_before']==old['source_subject_after']==q['source_subject']
copy(w/'workspace-check.log','initial-standard-container.log')
for p in initial.iterdir():copy(p,Path('initial-standard')/p.name)
r=w/'resumed-standard/report.json';report=json.loads(r.read_text())
assert report['result']=='pass-combined-same-inputs' and len(report['checks'])==120 and all(c['result']=='pass' for c in report['checks'])
assert report['source_subject_before']==report['source_subject_after']==q['source_subject']
for check in report['checks']:
 if 'log_sha256' in check:assert sha(r.parent/(check['name']+'.log'))==check['log_sha256']
for p in r.parent.iterdir():copy(p,Path('standard')/p.name)
for name in ['benchmark.py','benchmark.json','benchmark-run.log','benchmark-run-attempt-01.log','benchmark-driver-attempt-01.adb','baseline-benchmark-build-attempt-01.log','run_shared_preflight_benchmark.adb','bench.gpr','generate-media.py','media-inputs.json','regenerated-media-inputs.json','trace-benchmark.py','trace-benchmark.log','read-comparison.json','run-container.py','run-chaos-container.py','injection-tools.json','run-focused.py','focused.log','focused-map.log','focused-publication.log','candidate-build.log','finish-current.py','finish-current.log']:
 copy(b/name,Path('comparison')/name)
assert json.loads((b/'benchmark.json').read_text())['status']=='pass'
assert json.loads((b/'read-comparison.json').read_text())['result']=='pass'
for name,row in json.loads((b/'media-inputs.json').read_text()).items():assert sha(b/'media'/name)==row['sha256'] and (b/'media'/name).stat().st_size==row['size']
for label in ['baseline','candidate']:
 source_inputs=json.loads((b/(label+'-inputs.json')).read_text());differences=[]
 for name,digest in source_inputs.items():
  assert sha(b/label/'pkgcore'/name)==digest
  if inputs['pkgcore/'+name]!=digest:copy(b/label/'pkgcore'/name,Path('comparison')/label/'differing-inputs'/name);differences.append(name)
 copy(b/(label+'-inputs.json'),Path('comparison')/(label+'-inputs.json'))
 bench_inputs={**source_inputs}
 for name in ['bench.gpr','benchmark/run_shared_preflight_benchmark.adb']:bench_inputs[name]=sha(b/label/'pkgcore'/name)
 write('comparison/'+label+'-compiled-inputs.json',bench_inputs)
 write('comparison/'+label+'-differences.json',dict(different_from_final_pkgcore=differences,production_baseline_commit='3d618f309c2de39a1784c1fad65f2226c371e960' if label=='baseline' else None))
 for suffix in ['-benchmark-build.log','-reads.trace','-traced.log','-1.log','-16.log','-64.log']:copy(b/(label+suffix),Path('comparison')/(label+suffix))
baseline=root/'distribution/evidence/native-transition/publication-supply-01/workspace-inputs.json'
old=json.loads(baseline.read_text());c_inputs=[n for n in inputs if n.endswith(('.c','.h'))]
assert c_inputs and all(old.get(n)==inputs[n] for n in c_inputs)
write('unchanged-checks.json',dict(baseline='publication-supply-01',baseline_input_map_sha256=sha(baseline),c_input_count=len(c_inputs),all_c_inputs_unchanged=True,
 proof='seven exact input sets compared separately; no rerun',not_repeated=['native Python/image suite','private D-Bus','host duplicate source suite','C ASan/UBSan','134-case publication campaign'],scope='Prior results remain bound to their own source subject. New checks cover the changed map path, shared loss/recovery and actual publication callers. No new persistence format or write primitive.'))
print('Retained changed-path qualification and measured shared-reference reduction')
