# SPDX-License-Identifier: MIT
import hashlib, json, re, shutil, subprocess
from pathlib import Path
root = Path('/home/nia/devbox/niaos/nia-os-consent')
work = root.parent / '.work/native-generation-transition-01'
dest = root / 'distribution/evidence/native-transition/current-transition-01'
subject = subprocess.check_output(['python3', '-B', 'assurance/ci/engineering.py', 'subject'], cwd=root, text=True).strip()
inputs = json.loads((work / 'workspace-inputs.json').read_text())
current_inputs = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and not set(p.relative_to(root).parts) & {'.git', 'build', 'evidence', '__pycache__'}}
assert set(current_inputs) == set(inputs)
changed_inputs = [name for name in inputs if inputs[name] != current_inputs[name]]
assert set(changed_inputs) == {'AGENTS.md', 'STATUS.ja.md'}, changed_inputs
def copy(source, target):
    assert source.is_file() and not source.is_symlink() and source.stat().st_size <= 8 * 1024 * 1024, source
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert target.is_file() and not target.is_symlink() and target.stat().st_size <= 8 * 1024 * 1024, target
        if source.read_bytes() == target.read_bytes():
            return  # Preserve already copied immutable fixture modes.
    shutil.copy2(source, target)
accepted = (work / 'accepted-build-test.log').read_text()
assert sum(line.startswith('Running run_') for line in accepted.splitlines()) == 25
assert 'PASS assertions= 1361' in accepted and 'PASS assertions= 1193' in accepted
assert 'PASS assertions= 1361' in (work / 'sanitized.log').read_text()
assert not re.search(r'ERROR: AddressSanitizer|runtime error:', (work / 'sanitized.log').read_text())
oracle_rows = [json.loads(line) for line in accepted.splitlines() if line.startswith('{"result": "pass-for-two-published-native-catalog-observations"')]
assert len(oracle_rows) == 1
oracle = oracle_rows[0]
assert oracle == json.loads((work / 'reference-snapshot-result.json').read_text())
assert oracle['update_observations'] == 18 and len(oracle['update_bindings']) == 4 and oracle['missing_update_objects'] == 8
root_counts = [int(line.removeprefix('PASS assertions=')) for line in (work / 'root-probe.log').read_text().splitlines() if line.startswith('PASS assertions=')]
assert root_counts == [1113, 40, 3, 6, 8, 5, 5, 11], root_counts
assert json.loads((work / 'reproducibility.json').read_text())['binary_count'] == 29
assert json.loads((work / 'workspace-reproducibility.json').read_text())['binary_count'] == 18
assert re.findall(r'^Ran (\d+) tests', (work / 'private-dbus.log').read_text(), re.M) == ['32', '10']
assert json.loads((work / 'proof-input-comparison.json').read_text())['result'] == 'unchanged'
failed = work / 'workspace/assurance/evidence/engineering-trmsydn0/report.json'
whole = json.loads(failed.read_text())
assert whole['source_subject_before'] == subject
assert 'source_subject_after' not in whole  # Early source failure skips this observation.
assert whole['ada_execution'] == 'not-run'
assert [row['name'] for row in whole['checks'] if row['result'] != 'pass'] == ['engineering-unittests']
assert 'insufficient-memory-before-start' in (failed.parent / 'engineering-unittests.log').read_text()
for file in sorted(failed.parent.iterdir()):
    if file.is_file(): copy(file, dest / 'attempts/whole-gate-memory' / file.name)
files = ['.gitattributes', 'README.ja.md', 'accepted-build-test.log', 'root-probe.log', 'sanitized.log', 'private-dbus.log',
         'independent-build.log', 'independent-test-build.log', 'workspace-build.log', 'workspace-test-build.log',
         'reproducibility.json', 'workspace-reproducibility.json', 'elf.json', 'input-comparison.json',
         'build-inputs.json', 'workspace-inputs.json', 'workspace-supporting-docs.json', 'proof-input-comparison.json',
         'memory-before-first-build.json', 'registry-check.json', 'final-registry-check.log', 'final-lint.json',
         'reference-snapshot-result.json', 'prepare-qualification.py', 'run-container.py', 'run-independent-checks.py',
         'run-first-build.py', 'run-sanitized.py', 'capture-snapshot.py', 'compare-builds.py', 'compare-workspaces.py', 'check-proofs.py']
for name in files: copy(work / name, dest / name)
copy(work / 'workspace-check.log', dest / 'attempts/workspace-check.log')
copy(work / 'debug.log', dest / 'attempts/reboot-runroot-rejection.log')
copy(work / 'debug-build.log', dest / 'attempts/diagnostic-build-and-run.log')
debug = work / 'debug'
diagnostic_binary = debug / 'build/test-bin/run_generation_publication_tests'
independent_binary = work / 'workspace-independent-long-path/pkgcore/build/test-bin/run_generation_publication_tests'
assert diagnostic_binary.read_bytes() == independent_binary.read_bytes()
(dest / 'diagnostic-binary-comparison.json').write_text(json.dumps(dict(result='identical', sha256=hashlib.sha256(diagnostic_binary.read_bytes()).hexdigest(), scope='publication driver used for persisted reference snapshot and independent CI'), indent=2) + '\n')
debug_inputs = {str(p.relative_to(debug)): hashlib.sha256(p.read_bytes()).hexdigest() for p in debug.rglob('*') if p.is_file() and not set(p.relative_to(debug).parts) & {'.git', 'build', 'evidence', '__pycache__'}}
(dest / 'attempts/diagnostic-inputs.json').write_text(json.dumps(debug_inputs, indent=2) + '\n')
for name in ['runtime/pkg_generation_publisher.ads', 'runtime/pkg_generation_publisher.adb', 'tests/run_generation_publication_tests.adb', 'tests/compare_current_catalog.py']:
    copy(debug / name, dest / 'attempts/diagnostic-source' / name)
for file in sorted((work / 'reference-snapshot').rglob('*')):
    if file.is_file(): copy(file, dest / 'reference-snapshot' / file.relative_to(work / 'reference-snapshot'))
for name in ['compare_current_catalog.py', 'compare_catalog_store.py', 'compare_catalog_retention.py', 'compare_deb_payload.py', 'compare_payload_index.py', 'compare_selected_catalog.py']:
    copy(root / 'pkgcore/tests' / name, dest / 'readers' / name)
(dest / 'accepted-oracle.json').write_text(json.dumps(oracle, indent=2) + '\n')
(dest / 'handoff-only-changes.json').write_text(json.dumps(dict(changes=[dict(path=name, before_sha256=inputs[name], after_sha256=current_inputs[name], scope='handoff status only; excluded from engineering source subject; original build input map preserved') for name in sorted(changed_inputs)]), indent=2) + '\n')
report = dict(format=1, result='partial-qualification-host-memory-prerequisite', source_subject=subject,
              post_build_changes='handoff-only-changes.json',
              baseline_root_commit='313230d', source_gate_passed=False, whole_workspace_gate_passed=False,
              whole_gate='attempts/whole-gate-memory/report.json', whole_gate_failure='engineering-unittests: insufficient-memory-before-start',
              workspace_ada_mains_executed_by_whole_gate=0, workspace_apps_built=18,
              independent_pkgcore_mains_passed=25, pkgcore_executables_reproduced=29, workspace_apps_reproduced=18,
              publication_assertions=1361, stage_assertions=1193, root_driver_assertions=root_counts,
              update_observations=18, update_bindings=4, missing_update_objects=8, missing_baseline_retention_checks=64,
              private_dbus_tests=[32, 10], build_inputs=729, workspace_inputs=3346,
              proof_inputs='seven exact sets unchanged; affected runtime outside SPARK',
              sanitizer_scope='C boundaries and allocator/library-call interception only; Ada and upstream libraries uninstrumented; leaks disabled',
              production_authorization=False, physical_deb_payload_applied=False, boot_tested=False,
              full_capacity_qualified=False, safe_gc_implemented=False,
              remaining_required_checks=['complete whole-workspace source/build/71-main gate after real memory prerequisite recovers', 'host source gate'])
(dest / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
commands = dict(container_image='0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a', network='none', normal_uid=1000,
                root_uid=0, outer_scope='sh dev/run-limited.sh', limits=dict(memory_bytes=3221225472, swap_bytes=0, cpu_cores=1, pids=128),
                first='fresh workspace env -u TZ -u SOURCE_DATE_EPOCH make build JOBS=1; make -C pkgcore test-build JOBS=1',
                independent='fresh /independent-long-workspace make build JOBS=1; make -C pkgcore test-build JOBS=1',
                tested_binaries='independent build; byte-identical to first build', jobs=1, source_date_epoch=[None, 1788739200],
                independent_mtime=1788652800, timezones=['UTC default; explicit environment unset', 'Pacific/Honolulu'],
                new_dependencies=[], shared_runtime_changed=False, upstream_source_changed=False, safety_guard_changed=False)
(dest / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
copy(Path(__file__), dest / 'record-evidence.py')
files = sorted(p for p in dest.rglob('*') if p.is_file() and p.name != 'SHA256SUMS' and '__pycache__' not in p.parts)
assert all(p.stat().st_size <= 8 * 1024 * 1024 for p in files) and sum(p.stat().st_size for p in files) < 16 * 1024 * 1024
(dest / 'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + str(p.relative_to(dest)) + '\n' for p in files))
print('Recorded', len(files), 'bounded evidence files; partial qualification;', subject)
