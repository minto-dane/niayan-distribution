# SPDX-License-Identifier: MIT
import hashlib,json,shutil
from pathlib import Path
r=Path('/home/nia/devbox/niaos/nia-os-consent');w=r.parent/'.work/native-final-set-01';dest=r/'distribution/evidence/native-transition/final-set-01'
def copy(source,target):
 assert source.is_file() and not source.is_symlink() and source.stat().st_size<=8*1024*1024,source
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
source_path=Path((w/'source-check.log').read_text().splitlines()[-1]);source=json.loads(source_path.read_text())
assert source['result']=='pass-for-requested-layer-only' and len(source['checks'])==24 and all(c['result']=='pass' for c in source['checks'])
assert source['source_subject_before']==source['source_subject_after']
for p in sorted(source_path.parent.rglob('*')):
 if p.is_file():copy(p,dest/'source-checks'/p.relative_to(source_path.parent))
for name in ['accepted-build-test.log','independent-build.log','build-comparison.log','root-probe.log','sanitized.log','source-check.log','build-inputs.json','input-comparison.json','elf.json','reproducibility.json','proof-input-comparison.json','accepted-native-oracle.json','run-container.py','run-sanitized.py','compare-builds.py','check-proofs.py','upstream-oracle.py','upstream-oracle-898.log']:
 copy(w/name,dest/name)
for name in ['debug-run.log','debug-run-02.log','debug-run-03.log','debug-native-oracle.json','upstream-oracle.log']:
 copy(w/name,dest/'attempts'/name)
copy(w/'upstream-oracle-610/report.json',dest/'attempts/upstream-610-report.json')
copy(w/'upstream-oracle-610/case-0607/result.json',dest/'attempts/breaks-coinstalled-self-name.json')
copy(w/'upstream-oracle/report.json',dest/'upstream-report.json')
for name in ['compare_deb_final_set.py','check_deb_final_set_upstream.py','make_deb_final_set_fixtures.py']:
 copy(r/'pkgcore/tests'/name,dest/name)
copy(r/'pkgcore/tests/fixtures/deb-final-set/cases.json',dest/'cases.json')
copy(r/'pkgcore/tests/fixtures/deb-final-set/cases.txt',dest/'cases.txt')
records=[]
for p in sorted((w/'upstream-oracle').glob('case-*/result.json')):
 raw=p.read_bytes();row=json.loads(raw)
 assert (json.dumps(row,indent=2)+'\n').encode()==raw
 assert row['matches'] and all(len(run['stdout'])+len(run['stderr'])<=32768 for run in row['runs'])
 records.append(dict(sha256=hashlib.sha256(raw).hexdigest(),record=row))
assert len(records)==898
(dest/'upstream-cases.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in records))
upstream=json.loads((w/'upstream-oracle/report.json').read_text());assert upstream['cases']==898 and not upstream['mismatches']
native=json.loads((w/'accepted-native-oracle.json').read_text());assert native['cases']==898 and native['originals']==153
assert 'PASS assertions= 23038' in (w/'sanitized.log').read_text()
root_counts=[int(line.removeprefix('PASS assertions=')) for line in (w/'root-probe.log').read_text().splitlines() if line.startswith('PASS assertions=')]
assert root_counts==[1100,34,3,6,8,5]
assert len(json.loads((w/'build-inputs.json').read_text()))==677
report=dict(format=1,result='pass-for-candidate-endpoint-constraints-only',baseline_root_commit='ef2ca13',source_subject=source['source_subject_before'],source_report='source-checks/report.json',build_input_files=677,executables=27,ada_mains=23,new_assertions=23038,synthetic_originals=153,matrix_cases=898,findings=native['findings'],independent_native_hashes='accepted-native-oracle.json',upstream='upstream-report.json',upstream_mismatches=0,initial_upstream_mismatch='attempts/breaks-coinstalled-self-name.json',ci_includes=['fixture regeneration','native matrix','independent hashes','fixed upstream simulation'],root_driver_assertions=root_counts,proof_inputs='seven exact sets unchanged; new runtime outside SPARK',sanitizer_scope='C boundaries and allocator/library-call interception only; Ada and upstream library code uninstrumented; leaks disabled',full_capacity_qualified=False,real_os_package_set_qualified=False,production_authorization=False,phase_schedule_validated=False,essential_protected_removal_validated=False,effective_ownership_resolved=False,boot_tested=False)
(dest/'report.json').write_text(json.dumps(report,indent=2)+'\n')
commands=dict(container_image='0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a',network='none',normal_uid=1000,root_uid=0,outer_scope='sh dev/run-limited.sh',limits=dict(memory_bytes=3221225472,swap_bytes=0,cpu_cores=1,pids=128),normal='make compile-all build test JOBS=1',independent='make compile-all build test-build JOBS=1',root='sh ci/generation-root-refusal-test.sh',sanitized='python3 /evidence/run-sanitized.py',upstream='python3 tests/check_deb_final_set_upstream.py --media tests/fixtures/deb-final-set --work NEW_PRIVATE_PATH',source_date_epoch=1788739200,independent_mtime=1788652800,timezones=['UTC','Pacific/Honolulu'],new_dependencies=[],shared_runtime_changed=False,upstream_source_changed=False)
(dest/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
copy(Path(__file__),dest/'record-evidence.py')
files=sorted(p for p in dest.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts)
assert all(p.stat().st_size<=8*1024*1024 for p in files) and sum(p.stat().st_size for p in files)<16*1024*1024
(dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(dest))+'\n' for p in files))
print('Recorded',len(files),'bounded evidence files;',source['source_subject_before'])
