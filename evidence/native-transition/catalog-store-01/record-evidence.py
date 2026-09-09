# SPDX-License-Identifier: MIT
import hashlib,json,shutil
from pathlib import Path
r=Path('/home/nia/devbox/niaos/nia-os-consent');w=r.parent/'.work/native-catalog-store-01';dest=r/'distribution/evidence/native-transition/catalog-store-01'
def copy(source,target):
 assert source.is_file() and not source.is_symlink() and source.stat().st_size<=8*1024*1024,source
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
source_path=Path((w/'source-check.log').read_text().splitlines()[-1]);source=json.loads(source_path.read_text())
assert source['result']=='pass-for-requested-layer-only' and len(source['checks'])==24 and all(c['result']=='pass' for c in source['checks'])
assert source['source_subject_before']==source['source_subject_after']
for p in sorted(source_path.parent.rglob('*')):
 if p.is_file():copy(p,dest/'source-checks'/p.relative_to(source_path.parent))
for name in ['accepted-build-test.log','independent-build.log','build-comparison.log','root-probe.log','sanitized.log','source-check.log','build-inputs.json','input-comparison.json','elf.json','reproducibility.json','proof-input-comparison.json','run-container.py','run-sanitized.py','compare-builds.py','check-proofs.py']:
 copy(w/name,dest/name)
for name in ['debug.log','debug-02.log','debug-03.log','debug-oracle.json']:copy(w/name,dest/'attempts'/name)
copy(r/'pkgcore/tests/compare_catalog_store.py',dest/'compare_catalog_store.py')
accepted=(w/'accepted-build-test.log').read_text(); summaries=[json.loads(line) for line in accepted.splitlines() if line.startswith('{"result": "pass-for-persisted-catalog-and-reobserved-fixtures"')]
assert len(summaries)==1; native=summaries[0]
assert native['bytes']==440 and native['malformed_cases']==20
(dest/'accepted-oracle-summary.json').write_text(json.dumps(native,indent=2)+'\n')
reference=json.loads((w/'debug-oracle.json').read_text());assert all(reference[k]==v for k,v in native.items())
frame=bytes.fromhex(reference['frame_hex']);assert hashlib.sha256(frame).hexdigest()==native['address']
(dest/'catalog.bin').write_bytes(frame)
assert sum(line.startswith('Running run_') for line in accepted.splitlines())==25
assert 'PASS assertions= 320' in accepted and 'PASS assertions= 320' in (w/'sanitized.log').read_text()
root_counts=[int(line.removeprefix('PASS assertions=')) for line in (w/'root-probe.log').read_text().splitlines() if line.startswith('PASS assertions=')]
assert root_counts==[1100,34,3,6,8,5,5,7]
assert len(json.loads((w/'build-inputs.json').read_text()))==724
report=dict(format=1,result='pass-for-canonical-catalog-persistence-and-reobservation-only',baseline_root_commit='2469dac',source_subject=source['source_subject_before'],source_report='source-checks/report.json',build_input_files=724,executables=29,ada_mains=25,new_assertions=320,synthetic_originals=4,malformed_frames=20,catalog=native['address'],catalog_bytes=440,independent_native_hashes='accepted-oracle-summary.json',supplemental_reference='attempts/debug-oracle.json; includes complete frame whose address matches accepted CI',ci_includes=['native catalog persistence test','independent raw ar/tar payload and metadata oracle','direct saved CAS byte comparison'],root_driver_assertions=root_counts,proof_inputs='seven exact sets unchanged; new runtime outside SPARK',sanitizer_scope='C boundaries and allocator/library-call interception only; Ada and upstream library code uninstrumented; leaks disabled',full_capacity_qualified=False,real_os_package_set_qualified=False,production_authorization=False,accepted_generation_binding_validated=False,cas_pin_closure_validated=False,phase_schedule_validated=False,effective_ownership_resolved=False,boot_tested=False)
(dest/'report.json').write_text(json.dumps(report,indent=2)+'\n')
commands=dict(container_image='0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a',network='none',normal_uid=1000,root_uid=0,outer_scope='sh dev/run-limited.sh',limits=dict(memory_bytes=3221225472,swap_bytes=0,cpu_cores=1,pids=128),normal='make compile-all build test JOBS=1',independent='make compile-all build test-build JOBS=1',root='sh ci/generation-root-refusal-test.sh',sanitized='python3 /evidence/run-sanitized.py',source_date_epoch=1788739200,independent_mtime=1788652800,timezones=['UTC','Pacific/Honolulu'],new_dependencies=[],shared_runtime_changed=False,upstream_source_changed=False)
(dest/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');copy(Path(__file__),dest/'record-evidence.py')
files=sorted(p for p in dest.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts)
assert all(p.stat().st_size<=8*1024*1024 for p in files) and sum(p.stat().st_size for p in files)<16*1024*1024
(dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(dest))+'\n' for p in files))
print('Recorded',len(files),'bounded evidence files;',source['source_subject_before'])
