# SPDX-License-Identifier: MIT
import hashlib, json, re, shutil, subprocess
from pathlib import Path
r=Path('/home/nia/devbox/niaos/nia-os-consent'); w=r.parent/'.work/native-generation-retention-01'
dest=r/'distribution/evidence/native-transition/generation-retention-01'
def copy(source,target):
 assert source.is_file() and not source.is_symlink() and source.stat().st_size<=8*1024*1024,source
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
def report_checks(path):
 value=json.loads(path.read_text())
 assert value['result']=='pass-for-requested-layer-only' and all(c['result']=='pass' for c in value['checks'])
 assert value['source_subject_before']==value['source_subject_after']
 return value
source_path=Path((w/'source-check.log').read_text().splitlines()[-1]);source=report_checks(source_path)
assert len(source['checks'])==24
assert subprocess.check_output(['python3','-B',str(r/'assurance/ci/engineering.py'),'subject'],cwd=r,text=True).strip()==source['source_subject_before']
whole_paths=list((w/'workspace/assurance/evidence').glob('engineering-*/report.json'));assert len(whole_paths)==1
whole_path=whole_paths[0];whole=report_checks(whole_path)
assert whole['source_subject_before']==source['source_subject_before']
assert whole['ada_execution']=='all-registered-tests-pass'
assert len([c for c in whole['checks'] if c['layer'].startswith('ada-') and c['layer']!='ada-build'])==71
for path,name in [(source_path,'source-checks'),(whole_path,'workspace-checks')]:
 for p in sorted(path.parent.iterdir()):
  if p.is_file():copy(p,dest/name/p.name)
for name in ['README.ja.md','accepted-build-test.log','workspace-check.log','workspace-independent-build.log','build-comparison.log','workspace-build-comparison.log','root-probe.log','sanitized.log','source-check.log','build-inputs.json','workspace-inputs.json','workspace-supporting-docs.json','input-comparison.json','elf.json','reproducibility.json','workspace-reproducibility.json','proof-input-comparison.json','run-container.py','run-sanitized.py','remaining-checks.py','compare-builds.py','compare-workspaces.py','check-proofs.py','reference-snapshot-result.json']:
 copy(w/name,dest/name)
for name in ['debug','debug-02','debug-03','debug-04']:
 copy(w/(name+'.log'),dest/'attempts'/(name+'.log'))
 tree=w/name
 inputs={str(p.relative_to(tree)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tree.rglob('*') if p.is_file() and not set(p.relative_to(tree).parts)&{'.git','build','evidence','__pycache__'}}
 (dest/'attempts'/(name+'-inputs.json')).write_text(json.dumps(inputs,indent=2)+'\n')
 for rel in ['runtime/pkg_generation_manifest.adb','runtime/pkg_generation_manifest.ads','runtime/pkg_generation_stage.adb','runtime/pkg_generation_stage.ads','runtime/pkg_generation_publisher.adb','runtime/pkg_generation_publisher.ads','tests/run_generation_stage_tests.adb','tests/run_generation_publication_tests.adb','tests/compare_current_catalog.py']:
  copy(tree/rel,dest/'attempts'/name/rel)
for f in (w/'reference-snapshot').rglob('*'):
 if f.is_file():copy(f,dest/'reference-snapshot'/f.relative_to(w/'reference-snapshot'))
for name in ['compare_current_catalog.py','compare_catalog_store.py','compare_catalog_retention.py','compare_deb_payload.py','compare_payload_index.py','compare_selected_catalog.py']:
 copy(r/'pkgcore/tests'/name,dest/'readers'/name)
accepted=(w/'accepted-build-test.log').read_text()
rows=[json.loads(line) for line in accepted.splitlines() if line.startswith('{"result": "pass-for-two-published-native-catalog-observations"')]
assert len(rows)==1;native=rows[0]
assert native==json.loads((w/'reference-snapshot-result.json').read_text())
assert native['missing_retention_checks']==64 and native['observations']==16
assert [g['retention']['objects'] for g in native['generations']]==[5,7]
(dest/'accepted-oracle.json').write_text(json.dumps(native,indent=2)+'\n')
assert sum(line.startswith('Running run_') for line in accepted.splitlines())==25
assert 'PASS assertions= 1193' in accepted and 'PASS assertions= 1193' in (w/'sanitized.log').read_text()
assert 'PASS assertions= 1133' in accepted and 'PASS assertions= 1133' in (w/'sanitized.log').read_text()
root_counts=[int(line.removeprefix('PASS assertions=')) for line in (w/'root-probe.log').read_text().splitlines() if line.startswith('PASS assertions=')]
assert root_counts==[1113,37,3,6,8,5,5,11],root_counts
private_log=(w/'workspace-check.log').read_text();assert 'FAILED' not in private_log
assert re.findall(r'^Ran (\d+) tests',private_log,re.M)==['32','10']
assert json.loads((w/'workspace-reproducibility.json').read_text())['binary_count']==18
report=dict(format=1,result='pass-for-versioned-generation-catalog-retention-only',baseline_root_commit='af4142f',source_subject=source['source_subject_before'],source_report='source-checks/report.json',post_qualification_changes='handoff-only-changes.json',build_input_files=729,executables=29,ada_mains=25,stage_assertions=1193,publication_assertions=1133,native_observations=16,missing_retention_checks=64,closure_objects=[5,7],closure_bytes=[240,304],independent_oracle='accepted-oracle.json',root_driver_assertions=root_counts,proof_inputs='seven exact sets unchanged; affected runtime outside SPARK',sanitizer_scope='C boundaries and allocator/library-call interception only; Ada and upstream library code uninstrumented; leaks disabled',workspace_ada_mains=71,workspace_shipped_apps=18,private_dbus_tests=[32,10],workspace_python_unittest_discovered=580,workspace_python_unittest_skipped_in_source_checks=11,workspace_checks=len(whole['checks']),workspace_inputs=len(json.loads((w/'workspace-inputs.json').read_text())),workspace_report='workspace-checks/report.json',workspace_reproducibility='workspace-reproducibility.json',full_capacity_qualified=False,production_authorization=False,whole_generation_closure_validated=False,safe_gc_implemented=False,physical_deb_payload_applied=False,boot_tested=False)
(dest/'report.json').write_text(json.dumps(report,indent=2)+'\n')
commands=dict(container_image='0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a',network='none',normal_uid=1000,root_uid=0,outer_scope='sh dev/run-limited.sh',limits=dict(memory_bytes=3221225472,swap_bytes=0,cpu_cores=1,pids=128),normal='fresh workspace make check private-dbus JOBS=1, then sh pkgcore/ci/test-all.sh using those exact binaries',independent='fresh independent workspace make build JOBS=1, then make -C pkgcore test-build JOBS=1',root='sh pkgcore/ci/generation-root-refusal-test.sh',sanitized='python3 /evidence/run-sanitized.py',source_date_epoch=[None,1788739200],independent_mtime=1788652800,timezones=['UTC system default in cleaned build environment','Pacific/Honolulu'],fresh_build_trees_required=True,new_dependencies=[],shared_runtime_changed=False,upstream_source_changed=False)
(dest/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');copy(Path(__file__),dest/'record-evidence.py')
files=sorted(p for p in dest.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts)
assert all(p.stat().st_size<=8*1024*1024 for p in files) and sum(p.stat().st_size for p in files)<16*1024*1024
(dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(dest))+'\n' for p in files))
print('Recorded',len(files),'bounded evidence files;',report['source_subject'])
