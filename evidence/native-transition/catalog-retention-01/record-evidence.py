# SPDX-License-Identifier: MIT
import hashlib, json, shutil, re, subprocess
from pathlib import Path
r=Path('/home/nia/devbox/niaos/nia-os-consent'); w=r.parent/'.work/native-catalog-retention-01'
dest=r/'distribution/evidence/native-transition/catalog-retention-01'
def copy(source,target):
 assert source.is_file() and not source.is_symlink() and source.stat().st_size<=8*1024*1024,source
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
source_path=Path((w/'source-check.log').read_text().splitlines()[-1]);source=json.loads(source_path.read_text())
assert source['result']=='pass-for-requested-layer-only' and len(source['checks'])==24 and all(c['result']=='pass' for c in source['checks'])
assert source['source_subject_before']==source['source_subject_after']
assert subprocess.check_output(['python3','-B',str(r/'assurance/ci/engineering.py'),'subject'],cwd=r,text=True).strip()==source['source_subject_before']
for p in sorted(source_path.parent.rglob('*')):
 if p.is_file():copy(p,dest/'source-checks'/p.relative_to(source_path.parent))
for name in ['accepted-build-test.log','workspace-independent-build.log','build-comparison.log','root-probe.log','sanitized.log','source-check.log','build-inputs.json','input-comparison.json','elf.json','reproducibility.json','proof-input-comparison.json','run-container.py','run-sanitized.py','compare-builds.py','check-proofs.py']:
 copy(w/name,dest/name)
for name in ['debug.log','debug-02.log','debug-03.log','debug-oracle.json']:copy(w/name,dest/'attempts'/name)
copy(r/'pkgcore/tests/compare_catalog_retention.py',dest/'compare_catalog_retention.py')
accepted=(w/'accepted-build-test.log').read_text();rows=[json.loads(line) for line in accepted.splitlines() if line.startswith('{"result": "pass-for-two-exact-catalog-retention-closures"')]
assert len(rows)==1;native=rows[0];assert [x['objects'] for x in native['catalogs']]==[21,15]
assert native==json.loads((w/'debug-oracle.json').read_text())
(dest/'accepted-oracle.json').write_text(json.dumps(native,indent=2)+'\n')
assert sum(line.startswith('Running run_') for line in accepted.splitlines())==25
assert 'PASS assertions= 550' in accepted and 'PASS assertions= 550' in (w/'sanitized.log').read_text()
root_counts=[int(line.removeprefix('PASS assertions=')) for line in (w/'root-probe.log').read_text().splitlines() if line.startswith('PASS assertions=')]
assert root_counts==[1100,37,3,6,8,5,5,11]
assert len(json.loads((w/'build-inputs.json').read_text()))==729
snapshot=dest/'reference-snapshot';snapshot.mkdir(exist_ok=True)
for catalog in native['catalogs']:
 for digest in [catalog['address'],*catalog['member_sizes']]:
  object_path=w/'debug-store-03/objects'/digest[:2]/digest[2:];assert object_path.stat().st_size<=1024*1024
  raw=object_path.read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
  (snapshot/(digest+'.bin')).write_bytes(raw)
 copy(w/'debug-store-03/pins'/catalog['pin'],snapshot/(catalog['pin']+'.pin'))
whole_reports=list((w/'workspace/assurance/evidence').glob('engineering-*/report.json'));assert len(whole_reports)==1
whole_path=whole_reports[0];whole=json.loads(whole_path.read_text())
assert whole['result']=='pass-for-requested-layer-only' and whole['ada_execution']=='all-registered-tests-pass'
assert whole['source_subject_before']==whole['source_subject_after']==source['source_subject_before']
assert all(c['result']=='pass' for c in whole['checks'])
assert len([c for c in whole['checks'] if c['layer'].startswith('ada-') and c['layer']!='ada-build'])==71
for f in sorted(whole_path.parent.iterdir()):
 if f.is_file():copy(f,dest/'workspace-checks'/f.name)
for f in sorted((w/'pre-path-fix/workspace/assurance/evidence/engineering-tpzb7wpt').iterdir()):
 if f.name in ['report.json','engineering-unittests.log','unified-architecture-audit.log','syntax-and-doc-links.log']:
  copy(f,dest/'attempts/workspace-missing-supporting-docs'/f.name)
for f in sorted((w/'pre-path-fix/workspace/assurance/evidence/engineering-36ppcbzz').iterdir()):
 if f.name in ['report.json','pkgcore-run_generation_publication_tests.log']:
  copy(f,dest/'attempts/workspace-relative-media-path'/f.name)
for name in ['workspace-check.log','workspace-check-02.log']:
 copy(w/'pre-path-fix'/name,dest/'attempts'/name)
for name in ['workspace-check-final.log','workspace-independent-build.log','workspace-build-comparison.log','workspace-inputs.json','workspace-supporting-docs.json','workspace-reproducibility.json','compare-workspaces.py']:
 copy(w/name,dest/name)
private_log=(w/'workspace-check-final.log').read_text();assert 'FAILED' not in private_log
assert re.findall(r'^Ran (\d+) tests',private_log,re.M)==['32','10']
whole_repro=json.loads((w/'workspace-reproducibility.json').read_text());assert whole_repro['result']=='identical-binaries' and whole_repro['binary_count']==18
report=dict(format=1,result='pass-for-native-catalog-derived-retention-only',baseline_root_commit='bc3ba53',source_subject=source['source_subject_before'],source_report='source-checks/report.json',post_qualification_changes='handoff-only-changes.json',build_input_files=729,executables=29,ada_mains=25,catalog_driver_assertions=550,prior_catalog_driver_assertions=320,synthetic_originals=5,catalogs=2,closure_objects=[21,15],closure_bytes=[752,560],rejected_frames=35,missing_members=21,independent_oracle='accepted-oracle.json',root_driver_assertions=root_counts,proof_inputs='seven exact sets unchanged; new retention runtime outside SPARK',sanitizer_scope='C boundaries and allocator/library-call interception only; Ada and upstream library code uninstrumented; leaks disabled',full_capacity_qualified=False,real_os_package_set_qualified=False,production_authorization=False,workspace_ada_mains=71,workspace_shipped_apps=18,private_dbus_tests=[32,10],workspace_python_unittest_discovered=580,workspace_python_unittest_skipped_in_source_checks=11,workspace_checks=len(whole['checks']),workspace_inputs=len(json.loads((w/'workspace-inputs.json').read_text())),workspace_report='workspace-checks/report.json',workspace_reproducibility='workspace-reproducibility.json',private_dbus='workspace-check-final.log',whole_generation_closure_validated=False,safe_gc_implemented=False,physical_deb_payload_applied=False,boot_tested=False)
(dest/'report.json').write_text(json.dumps(report,indent=2)+'\n')
commands=dict(container_image='0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a',network='none',normal_uid=1000,root_uid=0,outer_scope='sh dev/run-limited.sh',limits=dict(memory_bytes=3221225472,swap_bytes=0,cpu_cores=1,pids=128),normal='fresh workspace make check private-dbus JOBS=1, then sh pkgcore/ci/test-all.sh using those exact binaries',independent='fresh independent workspace make build JOBS=1, then make -C pkgcore test-build JOBS=1',root='sh pkgcore/ci/generation-root-refusal-test.sh',sanitized='python3 /evidence/run-sanitized.py',source_date_epoch=[None,1788739200],independent_mtime=1788652800,timezones=['UTC system default in cleaned build environment','Pacific/Honolulu'],fresh_build_trees_required=True,new_dependencies=[],shared_runtime_changed=False,upstream_source_changed=False)
(dest/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');copy(Path(__file__),dest/'record-evidence.py')
files=sorted(p for p in dest.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts)
assert all(p.stat().st_size<=8*1024*1024 for p in files) and sum(p.stat().st_size for p in files)<16*1024*1024
(dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(dest))+'\n' for p in files))
print('Recorded',len(files),'bounded evidence files;',report['source_subject'])
