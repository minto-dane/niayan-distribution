# SPDX-License-Identifier: MIT
import hashlib, json
from pathlib import Path
root = Path('/home/nia/devbox/niaos/nia-os-consent')
work = root.parent / '.work/current-transition-qualification-02'
prior = root / 'distribution/evidence/native-transition/current-transition-01'
before = json.loads((prior / 'workspace-inputs.json').read_text())
after = json.loads((work / 'workspace-inputs.json').read_text())
assert set(before) == set(after)
changed = {name for name in before if before[name] != after[name]}
expected = {'AGENTS.md', 'STATUS.ja.md', 'assurance/docs/engineering/adr/ADR-0054.ja.md',
            'assurance/engineering/fault-cases.json', 'assurance/engineering/requirements.json',
            'assurance/tests/engineering/test_proof_guard.py'}
assert changed == expected, changed
pkg_inputs = json.loads((prior / 'build-inputs.json').read_text())
assert pkg_inputs == json.loads((work / 'build-inputs.json').read_text())
guard_paths = [name for name in after if name.endswith('/ci/proof-guard.py')]
guard_paths += ['dev/run-limited.sh', 'dev/limited-exec.py']
assert len(guard_paths) == 9 and all(before[name] == after[name] for name in guard_paths)
report = dict(result='exact-input-comparison', changed_inputs=[dict(path=name, before=before[name], after=after[name]) for name in sorted(changed)],
              prior_evidence='distribution/evidence/native-transition/current-transition-01',
              unchanged_pkgcore_input_count=len(pkg_inputs), unchanged_guard_and_scope_files={name: after[name] for name in guard_paths},
              runtime_and_ada_build_inputs_changed=False,
              meaning='Only fixture resource limits, their requirement/specification and prior handoff text changed; production guards and runtime inputs are byte-identical.')
(work / 'prior-input-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('Six explicit non-runtime input changes; 729 pkgcore inputs and all nine guard/scope files unchanged')
