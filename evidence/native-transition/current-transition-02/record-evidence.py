# SPDX-License-Identifier: MIT
import hashlib, json, re, shutil, subprocess
from pathlib import Path
root = Path('/home/nia/devbox/niaos/nia-os-consent')
work = root.parent / '.work/current-transition-qualification-02'
dest = root / 'distribution/evidence/native-transition/current-transition-02'
prior = root / 'distribution/evidence/native-transition/current-transition-01'
def copy(source, target):
    assert source.is_file() and not source.is_symlink() and source.stat().st_size <= 8 * 1024 * 1024, source
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() == source.read_bytes(): return
    shutil.copy2(source, target)
def accepted(path):
    report = json.loads(path.read_text())
    assert report['result'] == 'pass-for-requested-layer-only'
    assert all(row['result'] == 'pass' for row in report['checks'])
    assert report['source_subject_before'] == report['source_subject_after']
    return report
paths = list((work / 'workspace/assurance/evidence').glob('engineering-*/report.json'))
assert len(paths) == 1
whole_path = paths[0]; whole = accepted(whole_path)
source_path = Path((work / 'source-check.log').read_text().splitlines()[-1]); source = accepted(source_path)
subject = subprocess.check_output(['python3', '-B', 'assurance/ci/engineering.py', 'subject'], cwd=root, text=True).strip()
assert subject == whole['source_subject_before'] == source['source_subject_before']
assert len(whole['checks']) == 116 and len(source['checks']) == 24
assert whole['ada_execution'] == 'all-registered-tests-pass'
assert len([row for row in whole['checks'] if row['layer'].startswith('ada-') and row['layer'] != 'ada-build']) == 71
for source_dir, name in [(whole_path.parent, 'workspace-checks'), (source_path.parent, 'source-checks')]:
    for file in source_dir.iterdir():
        if file.is_file(): copy(file, dest / name / file.name)
assert 'PASS assertions= 1361' in (whole_path.parent / 'pkgcore-run_generation_publication_tests.log').read_text()
assert 'PASS assertions= 1193' in (whole_path.parent / 'pkgcore-run_generation_stage_tests.log').read_text()
assert re.findall(r'^Ran (\d+) tests', (work / 'workspace-check.log').read_text(), re.M) == ['32', '10']
count = skipped = 0
for row in source['checks']:
    if 'unittest' in row.get('argv', []):
        log = (source_path.parent / (row['name'] + '.log')).read_text()
        count += sum(map(int, re.findall(r'^Ran (\d+) tests?', log, re.M)))
        skipped += sum(map(int, re.findall(r'^OK \(skipped=(\d+)\)', log, re.M)))
assert count == 582 and skipped == 11, (count, skipped)
repro = json.loads((work / 'reproducibility.json').read_text())
assert repro['binary_count'] == 29
assert repro['binaries'] == json.loads((prior / 'reproducibility.json').read_text())['binaries']
assert json.loads((work / 'workspace-reproducibility.json').read_text())['binary_count'] == 18
assert json.loads((work / 'build-inputs.json').read_text()) == json.loads((prior / 'build-inputs.json').read_text())
prior_hashes = {}
for line in (prior / 'SHA256SUMS').read_text().splitlines():
    expected, name = line.split('  ', 1)
    assert hashlib.sha256((prior / name).read_bytes()).hexdigest() == expected
    prior_hashes[name] = expected
retained_checks = ['report.json', 'accepted-build-test.log', 'accepted-oracle.json', 'root-probe.log', 'sanitized.log', 'reproducibility.json', 'build-inputs.json', 'input-comparison.json']
binding = dict(result='same-pkgcore-inputs-and-executable-bytes', prior_directory='../current-transition-01',
               prior_root_commit='a273c41', prior_pkgcore_commit='795f503', pkgcore_input_count=729,
               identical_executable_count=29, checked_prior_files={name: prior_hashes[name] for name in retained_checks},
               meaning='Existing independent component CI, root refusal and sanitizer evidence retains its original source subject; current full-workspace execution is separately recorded. No new sanitizer or component-CI run is claimed.')
(dest / 'prior-pkgcore-evidence-binding.json').write_text(json.dumps(binding, indent=2) + '\n')
for name in ['README.ja.md', 'workspace-check.log', 'source-check.log', 'independent-build.log', 'independent-test-build.log',
             'build-comparison.log', 'workspace-build-comparison.log', 'build-inputs.json', 'workspace-inputs.json', 'workspace-supporting-docs.json',
             'reproducibility.json', 'workspace-reproducibility.json', 'elf.json', 'input-comparison.json', 'prior-input-comparison.json',
             'proof-input-comparison.json', 'run-container.py', 'prepare-qualification.py', 'remaining-checks.py',
             'compare-builds.py', 'compare-workspaces.py', 'compare-prior-inputs.py', 'check-proofs.py']:
    copy(work / name, dest / name)
report = dict(format=1, result='pass-for-development-gate-and-current-transition-only', source_subject=subject,
              source_checks=24, workspace_checks=116, workspace_ada_mains=71, workspace_apps=18,
              python_unittest_discovered=count, python_unittest_skipped_in_source_checks=skipped,
              guard_unit_tests=17, engineering_unit_tests=134, fixture_session_mib=128, reserve_mib=2048,
              default_prover_start_required_mib=4096, default_prover_session_mib=2048, production_guard_changed=False,
              private_dbus_tests=[32, 10], publication_assertions=1361, stage_assertions=1193,
              identical_pkgcore_executables=29, identical_workspace_apps=18, workspace_inputs=3346,
              source_report='source-checks/report.json', workspace_report='workspace-checks/report.json',
              unchanged_component_evidence='prior-pkgcore-evidence-binding.json',
              proof_inputs='seven exact sets unchanged; no new proof execution; generation runtime outside SPARK',
              production_authorization=False, physical_deb_payload_applied=False, boot_tested=False,
              full_capacity_qualified=False, apt_fully_replaced=False, all_languages_translated=False)
(dest / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
copy(Path(__file__), dest / 'record-evidence.py')
files = sorted(p for p in dest.rglob('*') if p.is_file() and p.name != 'SHA256SUMS' and '__pycache__' not in p.parts)
assert all(p.stat().st_size <= 8 * 1024 * 1024 for p in files) and sum(p.stat().st_size for p in files) < 16 * 1024 * 1024
(dest / 'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + str(p.relative_to(dest)) + '\n' for p in files))
print('Recorded', len(files), 'bounded evidence files;', subject)
