# SPDX-License-Identifier: MIT
import hashlib, json, re, shutil, subprocess
from pathlib import Path
root = Path('/home/nia/devbox/niaos/nia-os-consent')
work = root.parent / '.work/native-publication-intent-01'
dest = root / 'distribution/evidence/native-transition/publication-intent-01'
def copy(source, target):
    assert source.is_file() and not source.is_symlink() and source.stat().st_size <= 8 * 1024 * 1024, source
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() == source.read_bytes(): return
    shutil.copy2(source, target)
def accepted(path):
    value = json.loads(path.read_text())
    assert value['result'] == 'pass-for-requested-layer-only' and all(c['result'] == 'pass' for c in value['checks'])
    assert value['source_subject_before'] == value['source_subject_after']
    return value
source_path = Path((work / 'source-check.log').read_text().splitlines()[-1]); source = accepted(source_path)
whole_paths = list((work / 'workspace/assurance/evidence').glob('engineering-*/report.json')); assert len(whole_paths) == 1
whole_path = whole_paths[0]; whole = accepted(whole_path)
assert len(source['checks']) == 24 and len(whole['checks']) == 116
assert whole['ada_execution'] == 'all-registered-tests-pass'
assert len([c for c in whole['checks'] if c['layer'].startswith('ada-') and c['layer'] != 'ada-build']) == 71
subject = subprocess.check_output(['python3', '-B', 'assurance/ci/engineering.py', 'subject'], cwd=root, text=True).strip()
assert source['source_subject_before'] == whole['source_subject_before'] == subject
for path, name in [(source_path, 'source-checks'), (whole_path, 'workspace-checks')]:
    for file in sorted(path.parent.iterdir()):
        if file.is_file(): copy(file, dest / name / file.name)
for name in ['.gitattributes', 'README.ja.md', 'workspace-check.log', 'independent-build.log', 'independent-test-build.log',
             'accepted-build-test.log', 'build-comparison.log', 'workspace-build-comparison.log', 'root-probe.log', 'sanitized.log', 'source-check.log',
             'build-inputs.json', 'workspace-inputs.json', 'workspace-supporting-docs.json', 'input-comparison.json', 'elf.json',
             'reproducibility.json', 'workspace-reproducibility.json', 'proof-input-comparison.json', 'reference-snapshot-result.json',
             'run-container.py', 'run-sanitized.py', 'remaining-checks.py', 'finish-checks.py', 'prepare-qualification.py',
             'compare-builds.py', 'compare-workspaces.py', 'check-proofs.py', 'capture-snapshot.py']:
    copy(work / name, dest / name)
for attempt in ['debug', 'debug-02', 'debug-03', 'debug-04']:
    copy(work / (attempt + '.log'), dest / 'attempts' / (attempt + '.log'))
    tree = work / attempt
    inputs = {str(p.relative_to(tree)): hashlib.sha256(p.read_bytes()).hexdigest() for p in tree.rglob('*') if p.is_file() and not set(p.relative_to(tree).parts) & {'.git', 'build', 'evidence', '__pycache__'}}
    (dest / 'attempts' / (attempt + '-inputs.json')).write_text(json.dumps(inputs, indent=2) + '\n')
    for name in ['runtime/pkg_generation_intent.ads', 'runtime/pkg_generation_intent.adb', 'runtime/pkg_generation_manifest.ads',
                 'runtime/pkg_generation_manifest.adb', 'runtime/pkg_generation_stage.adb', 'runtime/pkg_generation_publisher.ads',
                 'runtime/pkg_generation_publisher.adb', 'tests/run_generation_stage_tests.adb', 'tests/run_generation_publication_tests.adb', 'tests/compare_current_catalog.py']:
        copy(tree / name, dest / 'attempts' / attempt / name)
copy(work / 'debug-oracle.json', dest / 'attempts/debug-04-oracle.json')
for file in (work / 'reference-snapshot').rglob('*'):
    if file.is_file(): copy(file, dest / 'reference-snapshot' / file.relative_to(work / 'reference-snapshot'))
for name in ['compare_current_catalog.py', 'compare_catalog_store.py', 'compare_catalog_retention.py', 'compare_deb_payload.py', 'compare_payload_index.py', 'compare_selected_catalog.py']:
    copy(root / 'pkgcore/tests' / name, dest / 'readers' / name)
ci = (work / 'accepted-build-test.log').read_text()
rows = [json.loads(line) for line in ci.splitlines() if line.startswith('{"result": "pass-for-two-published-native-catalog-observations"')]
assert len(rows) == 1
oracle = rows[0]; assert oracle == json.loads((work / 'reference-snapshot-result.json').read_text())
assert oracle['observations'] == 16 and oracle['update_observations'] == 18
assert oracle['missing_retention_checks'] == 73 and oracle['missing_update_objects'] == 8
assert oracle['intent_reject_cases'] == 26 and oracle['intent_publication_rejections'] == 3
assert len(oracle['publication_intents']) == 2 and len(oracle['update_bindings']) == 4
assert sum(line.startswith('Running run_') for line in ci.splitlines()) == 25
for count in [1202, 1638]:
    assert 'PASS assertions= ' + str(count) in ci
    assert 'PASS assertions= ' + str(count) in (work / 'sanitized.log').read_text()
root_counts = [int(line.removeprefix('PASS assertions=')) for line in (work / 'root-probe.log').read_text().splitlines() if line.startswith('PASS assertions=')]
assert root_counts == [1122, 43, 3, 6, 8, 5, 5, 11], root_counts
assert re.findall(r'^Ran (\d+) tests', (work / 'workspace-check.log').read_text(), re.M) == ['32', '10']
assert json.loads((work / 'reproducibility.json').read_text())['binary_count'] == 29
assert json.loads((work / 'workspace-reproducibility.json').read_text())['binary_count'] == 18
assert len(json.loads((work / 'workspace-inputs.json').read_text())) == 3350
assert len(json.loads((work / 'build-inputs.json').read_text())) == 731
(dest / 'accepted-oracle.json').write_text(json.dumps(oracle, indent=2) + '\n')
report = dict(format=1, result='pass-for-retained-native-intent-publication-only', baseline_root_commit='181ff42', source_subject=subject,
              source_report='source-checks/report.json', workspace_report='workspace-checks/report.json', source_checks=24, workspace_checks=116,
              workspace_ada_mains=71, workspace_apps=18, pkgcore_ada_mains=25, stage_assertions=1202, publication_assertions=1638,
              native_observations=16, update_observations=18, update_bindings=4, publication_intents=2,
              intent_reject_cases=26, intent_publication_rejections=3, missing_retention_checks=73, missing_update_objects=8,
              root_driver_assertions=root_counts, private_dbus_tests=[32, 10], python_unittest_discovered=582, python_unittest_skipped_in_source_checks=11,
              pkgcore_build_inputs=731, workspace_inputs=3350, identical_pkgcore_executables=29, identical_workspace_apps=18,
              reference_snapshot_run='ASan/UBSan publication run; independent oracle matches ordinary component CI exactly',
              proof_inputs='seven exact sets unchanged; changed runtime outside SPARK; no repeated proof execution',
              sanitizer_scope='C boundaries and allocator/library-call interception; Ada and upstream library bodies uninstrumented; leaks disabled',
              production_authorization=False, physical_deb_payload_applied=False, boot_tested=False, full_capacity_qualified=False,
              legacy_live_migration_qualified=False, safe_gc_implemented=False, apt_fully_replaced=False, all_languages_translated=False)
(dest / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
commands = dict(image='0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a', network='none', normal_uid=1000, root_uid=0,
                outer_scope='sh dev/run-limited.sh', memory_bytes=3221225472, swap_bytes=0, cpu_cores=1, pids=128, jobs=1,
                normal='fresh workspace make check private-dbus JOBS=1; independent pkgcore CI uses these same binaries',
                independent='fresh /independent-long-workspace make build JOBS=1; make -C pkgcore test-build JOBS=1',
                source_date_epoch=[None,1788739200], timezones=['UTC default; full runner removes TZ', 'Pacific/Honolulu'], independent_mtime=1788652800,
                new_dependencies=[], upstream_source_changed=False, shared_runtime_changed=False, safety_limits_changed=False)
(dest / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n'); copy(Path(__file__), dest / 'record-evidence.py')
files = sorted(p for p in dest.rglob('*') if p.is_file() and p.name != 'SHA256SUMS' and '__pycache__' not in p.parts)
assert all(p.stat().st_size <= 8 * 1024 * 1024 for p in files) and sum(p.stat().st_size for p in files) < 16 * 1024 * 1024
(dest / 'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + str(p.relative_to(dest)) + '\n' for p in files))
print('Recorded', len(files), 'bounded evidence files;', subject)
