# SPDX-License-Identifier: MIT
import hashlib,json,shutil
from pathlib import Path
r=Path('/home/nia/devbox/niaos/nia-os-consent'); w=r.parent/'.work/native-catalog-01'; dest=r/'distribution/evidence/native-transition/selected-catalog-01'
def copy(source,target):
 assert source.is_file() and not source.is_symlink() and source.stat().st_size <= 8*1024*1024,source
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
report_path=Path((w/'source-check.log').read_text().splitlines()[-1]); source=json.loads(report_path.read_text())
assert source['result']=='pass-for-requested-layer-only' and len(source['checks'])==24 and all(c['result']=='pass' for c in source['checks'])
assert source['source_subject_before']==source['source_subject_after']
for p in sorted(report_path.parent.rglob('*')):
 if p.is_file():copy(p,dest/'source-checks'/p.relative_to(report_path.parent))
names=['accepted-build-test.log','independent-build.log','build-comparison.log','root-probe.log','sanitized.log','observations.log','source-check.log','build-inputs.json','input-comparison.json','elf.json','reproducibility.json','proof-input-comparison.json','run-container.py','run-observations.py','run-sanitized.py','probe-all.py','probe-resources.py','compare-builds.py','check-proofs.py','fixture-list.txt','fixture-reverse.txt','original-list.txt','reference-original-index.json','fixture-index.log','fixture-index-resources.json','fixture-index-oracle.json']
for name in names:copy(w/name,dest/name)
for name in ['catalog-fixtures','catalog-reverse','catalog-originals']:
 for suffix in ['.log','-resources.json','-oracle.json']:copy(w/(name+suffix),dest/(name+suffix))
for p in sorted((w/'fixture-probes').iterdir()):
 if p.is_file():copy(p,dest/'fixture-probes'/p.name)
for name in ['original-media-inputs.json','large-input.json']:copy(w.parent/'native-data-stream-01'/name,dest/name)
for name in ['compare_selected_catalog.py','compare_deb_payload.py','compare_payload_index.py']:copy(r/'pkgcore/tests'/name,dest/name)
for name in ['debug-build.log','debug-run.log','debug-test.log']:copy(w/name,dest/'attempts'/name)
fixtures=json.loads((w/'catalog-fixtures-oracle.json').read_text());reverse=json.loads((w/'catalog-reverse-oracle.json').read_text());originals=json.loads((w/'catalog-originals-oracle.json').read_text())
assert fixtures['result']==reverse['result']==originals['result']=='pass'
assert fixtures['hashes']==reverse['hashes'] and fixtures['packages']==4 and fixtures['atoms']==15
reference=json.loads((w/'reference-original-index.json').read_text()); expected={x['filename']:x['original'] for x in reference['independent_payload_checks']}
assert {x['filename']:x['original'] for x in originals['originals']}==expected
assert originals['hashes']['PAYLOAD']==reference['index']['INDEX'] and originals['packages']==14
assert len(json.loads((w/'build-inputs.json').read_text()))==516
resources={name:json.loads((w/(name+'-resources.json')).read_text()) for name in ['catalog-fixtures','catalog-reverse','catalog-originals']}
assert all(x['returncode']==0 for x in resources.values())
assert 'PASS assertions= 313' in (w/'sanitized.log').read_text()
root_counts=[int(l.removeprefix('PASS assertions=')) for l in (w/'root-probe.log').read_text().splitlines() if l.startswith('PASS assertions=')]
assert root_counts==[1100,34,3,6,8],root_counts
record=dict(format=1,result='pass-for-private-selected-candidate-binding-only',baseline_root_commit='d3e21ba',source_subject=source['source_subject_before'],source_report='source-checks/report.json',build_input_files=516,executables=26,ada_mains=22,new_assertions=313,fixture_regeneration=7,synthetic=fixtures,original_media=originals,resources=resources,root_driver_assertions=root_counts,proof_inputs='seven exact existing sets unchanged; new runtime outside SPARK',sanitizer_scope='C boundaries and allocator/library-call interception only; Ada and upstream library code uninstrumented; leaks disabled',payload_reference='previous independently qualified original-media index, reobserved by the new native scan and bound to exactly the same original hashes; new synthetic index independently checked in this run',production_authorization=False,full_os_capacity_qualified=False,installed_catalog=False,relationships_satisfied=False,effective_ownership_resolved=False,boot_tested=False)
(dest/'report.json').write_text(json.dumps(record,indent=2)+'\n')
commands=dict(container_image='0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a',network='none',normal_uid=1000,root_uid=0,outer_scope='sh dev/run-limited.sh',limits=dict(memory_bytes=3221225472,swap_bytes=0,cpu_cores=1,pids=128),normal='make compile-all build test JOBS=1',independent='make compile-all build test-build JOBS=1',root='sh ci/generation-root-refusal-test.sh',observations='python3 /evidence/run-observations.py',sanitized='python3 /evidence/run-sanitized.py',source_date_epoch=1788739200,independent_mtime=1788652800,timezones=['UTC','Pacific/Honolulu'],new_dependencies=[],shared_runtime_changed=False,upstream_source_changed=False)
(dest/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
copy(Path(__file__),dest/'record-evidence.py')
files=sorted(p for p in dest.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts)
assert sum(p.stat().st_size for p in files)<16*1024*1024
(dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(dest))+'\n' for p in files))
print('Recorded',len(files),'bounded evidence files;',source['source_subject_before'])
