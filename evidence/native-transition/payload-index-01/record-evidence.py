# SPDX-License-Identifier: MIT
import hashlib,json,shutil
from pathlib import Path
root=Path('/home/nia/devbox/niaos/nia-os-consent');base=root.parent/'.work/native-payload-index-01';dest=root/'distribution/evidence/native-transition/payload-index-01'

def copy(source,target):
    assert source.is_file() and not source.is_symlink() and source.stat().st_size<=8*1024*1024,source
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)

checks=[]
for name,log in [('source-checks-first','source-check.log'),('source-checks-pre-clarification','source-check-final.log'),('source-checks-final','source-check-final-02.log')]:
    report=Path((base/log).read_text().splitlines()[-1]);data=json.loads(report.read_text())
    assert data['result']=='pass-for-requested-layer-only' and len(data['checks'])==24 and all(c['result']=='pass' for c in data['checks'])
    assert data['source_subject_before']==data['source_subject_after']
    for p in sorted(report.parent.rglob('*')):
        if p.is_file():copy(p,dest/name/p.relative_to(report.parent))
    checks.append({'report':name+'/report.json','subject':data['source_subject_before']})

names=['accepted-build-test.log','independent-build.log','build-comparison.log','root-probe.log','sanitized.log','fixture-oracles.log','original-oracles.log','source-check.log','source-check-final.log','source-check-final-02.log','fixture-reproduction.log','build-inputs.json','input-comparison.json','elf.json','reproducibility.json','proof-input-comparison.json','run-container.py','run-corpus.py','run-sanitized.py','probe-all.py','probe-resources.py','compare-builds.py','check-proofs.py']
for name in names:copy(base/name,dest/name)
for name in ['compare_deb_payload.py','compare_payload_index.py']:copy(root/'pkgcore/tests'/name,dest/name)
for group in ['retained-fixtures','retained-originals']:
    for p in sorted((base/group).iterdir()):
        if p.is_file():copy(p,dest/group/p.name)
    for direction in ['forward','reverse']:
        for suffix in ['.txt','.log','-resources.json','-oracle.json']:
            name=group+'-'+direction+suffix;copy(base/name,dest/name)
for name in ['original-media-inputs.json','large-input.json']:copy(root.parent/'.work/native-data-stream-01'/name,dest/name)
for name in ['debug-build.log','debug-test.log']:copy(base/name,dest/'attempts'/name)

fixtures=json.loads((base/'retained-fixtures-forward-oracle.json').read_text());originals=json.loads((base/'retained-originals-forward-oracle.json').read_text())
assert fixtures['index']['PACKAGES']==14 and fixtures['index']['CLAIMS']==35 and fixtures['index']['PATHS']==28
assert originals['index']['PACKAGES']==14 and originals['index']['CLAIMS']==2904 and originals['index']['PATHS']==2493
for group,forward in [('retained-fixtures',fixtures),('retained-originals',originals)]:
    reverse=json.loads((base/(group+'-reverse-oracle.json')).read_text());assert forward['index']==reverse['index']
    for direction in ['forward','reverse']:
        resource=json.loads((base/(group+'-'+direction+'-resources.json')).read_text());assert resource['returncode']==0
inputs=json.loads((base.parent/'native-data-stream-01/original-media-inputs.json').read_text())['files']
expected={r['filename']:r['sha256'] for r in inputs};large=json.loads((base.parent/'native-data-stream-01/large-input.json').read_text())
# Large synthetic source is included in the independently checked original media.
checked={r['filename']:r['original'] for r in originals['independent_payload_checks']}
assert len(expected)==13 and len(checked)==14
assert all(checked.get(name)==value for name,value in expected.items())
assert checked[large['filename']]==large['sha256']
assert next(r for r in originals['independent_payload_checks'] if r['filename']==large['filename'])['tar']==large['expanded_sha256']
resources={group:{direction:json.loads((base/(group+'-'+direction+'-resources.json')).read_text()) for direction in ['forward','reverse']} for group in ['retained-fixtures','retained-originals']}
report=dict(format=1,result='pass-for-private-source-claim-index-only',baseline_root_commit='27d9a4d',source_checks=checks,build_input_files=503,executables=25,ada_mains=21,new_assertions=449,fixture_regeneration=3,synthetic_index=fixtures['index'],original_media_index=originals['index'],total_original_tar_bytes=sum(r['tar_bytes'] for r in originals['independent_payload_checks']),resources=resources,root_driver_assertions=[1100,34,3,6],proof_inputs='seven exact sets unchanged; new runtime outside SPARK',sanitizer_scope='C boundaries and allocator/library-call interception only; Ada and upstream library code uninstrumented; leaks disabled',production_authorization=False,full_os_capacity_qualified=False,installed_catalog=False,effective_ownership_resolved=False,boot_tested=False)
(dest/'report.json').write_text(json.dumps(report,indent=2)+'\n')
commands=dict(container_image='0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a',network='none',normal_uid=1000,root_uid=0,outer_scope='sh dev/run-limited.sh',limits=dict(memory_bytes=3221225472,swap_bytes=0,cpu_cores=1,pids=128),normal='make compile-all build test JOBS=1',independent='make compile-all build test-build JOBS=1',root='sh ci/generation-root-refusal-test.sh',fixtures='python3 tests/make_payload_index_fixtures.py --check',corpus='python3 /evidence/run-corpus.py GROUP MEDIA',sanitized='python3 /evidence/run-sanitized.py',source_date_epoch=1788739200,independent_mtime=1788652800,timezones=['UTC','Pacific/Honolulu'],new_dependencies=[],shared_runtime_changed=False,upstream_source_changed=False)
(dest/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
copy(Path(__file__),dest/'record-evidence.py')
files=sorted(p for p in dest.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts)
assert sum(p.stat().st_size for p in files)<16*1024*1024
(dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(dest))+'\n' for p in files))
print('Recorded',len(files),'bounded evidence files;',checks[-1]['subject'])
