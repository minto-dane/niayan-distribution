# SPDX-License-Identifier: MIT
import hashlib,json,re,shutil,subprocess
from pathlib import Path
root=Path('/home/nia/devbox/niaos/nia-os-consent');work=root.parent/'.work/native-archive-supply-01'
dest=root/'distribution/evidence/native-transition/archive-supply-01'
def copy(source,target):
    assert source.is_file() and not source.is_symlink() and source.stat().st_size<=8*1024*1024,source
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and target.read_bytes()==source.read_bytes():return
    shutil.copy2(source,target)
subject=subprocess.check_output(['python3','-B','assurance/ci/engineering.py','subject'],cwd=root,text=True).strip()
assert subject=='aac58be4b71cb2356b1db2d5e55d371125483df1797d360882b4cd82076c3e5b'
reports={}
for kind in ['container','host']:
    path=Path((work/(kind+'-source-check.log')).read_text().splitlines()[-1])
    if str(path).startswith('/workspace/'):path=work/'workspace'/path.relative_to('/workspace')
    data=json.loads(path.read_text());reports[kind]=data
    assert data['result']=='pass-for-requested-layer-only' and len(data['checks'])==24
    assert all(c['result']=='pass' for c in data['checks'])
    assert data['source_subject_before']==data['source_subject_after']==subject
    logs=list(path.parent.glob('*.log'))
    assert sum(sum(map(int,re.findall(r'^Ran (\d+) tests',p.read_text(),re.M))) for p in logs)==597
    assert sum(len(re.findall(r'\.\.\. skipped',p.read_text())) for p in logs)==11
    for p in path.parent.iterdir():
        if p.is_file():copy(p,dest/(kind+'-source-checks')/p.name)
native=(work/'native-image-check.log').read_text()
assert re.findall(r'^Ran (\d+) tests',native,re.M)==['173','134','4','16']
assert len(re.findall(r'^OK$',native,re.M))==4 and 'skipped' not in native
assert 'PASS exact offline replay' in (work/'official-offline-replay.log').read_text()
assert 'PASS real UID0 refusal before supply access' in (work/'root-refusal.log').read_text()
assert sum(s.startswith('PASS public command:') for s in (work/'download-cli.log').read_text().splitlines())==6
inputs=json.loads((work/'input-comparison.json').read_text());assert inputs['result']=='pass'
assert len(inputs['copies'])==2 and all(c['inputs']==3355 and c['matches'] for c in inputs['copies'])
assert len(inputs['unchanged_component_inputs'])==7 and all(c['unchanged'] for c in inputs['unchanged_component_inputs'])
assert json.loads((work/'proof-input-comparison.json').read_text())['result']=='unchanged'
for name in ['README.ja.md','.gitattributes','native-image.id','native-image-build.log','native-image-packages.log',
             'native-image-check.log','official.log','official-offline-replay.log','root-refusal.log','download-cli.log',
             'container-source-check.log','host-source-check.log','workspace-inputs.json','workspace-supporting-docs.json',
             'input-comparison.json','proof-input-comparison.json','prepare-checks.py','run-checks.py','run-container.py',
             'observe-official.py','replay-official.py','compare-inputs.py','check-proofs.py']:
    copy(work/name,dest/name)
for p in sorted((work/'official').rglob('*')):
    if p.is_file():copy(p,dest/'official'/p.relative_to(work/'official'))
for name in ['native-image.id','native-image-build.log','native-image-check.log','native-tool-check.log',
             'workspace-inputs.json','workspace-supporting-docs.json']:
    copy(work/(name+'-01'),dest/'attempts'/name)
for name in ['Containerfile','test-packages.txt']:
    copy(work/'build-context-01/native'/name,dest/'attempts/build-context/native'/name)
    copy(work/'build-context/native'/name,dest/'build-context/native'/name)
for name in ['Makefile','native/archive-supply.ja.md','native/archive_intake.py','native/test_archive_intake.py',
             'tests/test_debian_trust.py','tools/debian_archive_auth.py','tools/deb_archive.py']:
    copy(work/'workspace-01/distribution'/name,dest/'attempts/source'/name)
old=(work/'native-tool-check.log-01').read_text();assert "No such file or directory: 'zstd'" in old and 'FAILED (errors=1)' in old
for name in ['debian_archive_auth.py','deb_archive.py','nia_common.py','debian_semantics.py','debian_triggers.py']:
    copy(root/'distribution/tools'/name,dest/'readers'/name)
official=json.loads((work/'official/observations.json').read_text())
assert len(official['observations']['source']['source_manifest']['files'])==3
report={'format':1,'result':'pass-for-debian13-archive-supply-observation-only','baseline_root_commit':'c015455',
        'source_subject':subject,'source_checks':{'container':24,'host':24},'source_python_tests_discovered':597,'source_skipped_each':11,
        'native_image_tests':{'tools':173,'native':134,'hardening':4,'image':16},'public_download_cli_cases':6,
        'archive_root_refusal':True,'new_openpgp_tests':15,'new_tuf_archive_tests':12,
        'official_releases':['trixie','trixie-updates','trixie-security'],'official_binary':official['observations']['binary']['observation']['identity'],
        'official_source_files':3,'official_offline_replay':'exact observations at original observation time',
        'native_test_image':(work/'native-image.id').read_text().strip(),'development_image':'0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a',
        'source_inputs':3355,'identical_source_copies':2,'component_code_build_test_input_sets_unchanged':7,'proof_input_sets_unchanged':7,
        'new_ada_build':False,'new_ada_execution':False,'new_formal_proof':False,'new_binary_reproducibility_run':False,
        'production_policy_provisioned':False,'rollback_resistant_trust_floor_implemented':False,'native_cas_plan_binding_implemented':False,
        'production_admission_implemented':False,'physical_deb_payload_applied':False,'boot_tested':False,'apt_fully_replaced':False,'all_languages_translated':False}
(dest/'report.json').write_text(json.dumps(report,indent=2)+'\n')
commands={'limits':{'memory_bytes':3221225472,'swap_bytes':0,'cpu_cores':1,'pids':128},'serial_execution':True,
          'network':'enabled only for pinned test-image builds and bounded official artifact acquisition; disabled in qualification containers',
          'native_image_command':'make image-check','source_commands':'run-engineering-checks.py --mode source in fixed development image and host',
          'new_dependencies_scope':'test image only: dpkg, gnupg, gpgv, zstd; no development host package installation',
          'upstream_source_changed':False,'ada_runtime_changed':False,'security_limits_changed':False,
          'first_attempt':'missing zstd in separate tool check; preserved, fixed dependency and CI target, rebuilt image and used fresh workspace'}
(dest/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');copy(Path(__file__),dest/'record-evidence.py')
files=sorted(p for p in dest.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
assert all(not p.is_symlink() and p.stat().st_size<=8*1024*1024 for p in files)
assert sum(p.stat().st_size for p in files)<16*1024*1024
(dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(dest))+'\n' for p in files))
print('Recorded',len(files),'bounded evidence files for',subject)
