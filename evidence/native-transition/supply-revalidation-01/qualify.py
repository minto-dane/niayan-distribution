# SPDX-License-Identifier: MIT
"""Sequential fixed-image qualification of the retained-metadata change."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path('/home/nia/devbox/niaos/nia-os-consent')
work = Path(__file__).resolve().parent
workspace = work/'workspace'
excluded = {'.git', 'build', 'evidence', '__pycache__', '.pytest_cache'}
inputs = {}
workspace.mkdir()
for parent, dirs, files in os.walk(root, followlinks=False):
    dirs[:] = sorted(d for d in dirs if d not in excluded)
    for name in sorted(files):
        source = Path(parent)/name
        if name in excluded or name.endswith('.pyc'):
            continue
        assert not source.is_symlink() and source.stat().st_size <= 8*1024*1024, source
        relative = str(source.relative_to(root))
        inputs[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
        target = workspace/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
(work/'workspace-inputs.json').write_text(json.dumps(inputs, indent=2)+'\n')
support = json.loads((root.parent/'.work/native-archive-supply-01/workspace-supporting-docs.json').read_text())
for name, expected in support.items():
    source = root/name
    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
    target = workspace/name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
(work/'workspace-supporting-docs.json').write_text(json.dumps(support, indent=2)+'\n')
sys.path.insert(0, str(root/'assurance/ci'))
import engineering
subject = engineering.source_subject(root)
assert engineering.source_subject(workspace) == subject
image = 'sha256:b626ca976c8ba342df3377e3ad068e29bf45b4c3ad0f7f8927f0551dd09c07dd'
dev_image = 'sha256:0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a'
report = {'source_subject': subject, 'result': 'running', 'inputs': len(inputs),
          'native_image': image, 'dev_image': dev_image, 'checks': [],
          'production_approval': False, 'ada_execution': 'not-repeated', 'formal_proof': 'not-repeated'}
def run(name, command):
    print('Starting '+name, flush=True)
    with (work/(name+'.log')).open('x') as output:
        result = subprocess.run(command, cwd=root, stdout=output, stderr=subprocess.STDOUT)
    report['checks'].append({'name': name, 'returncode': result.returncode,
                            'log_sha256': hashlib.sha256((work/(name+'.log')).read_bytes()).hexdigest()})
    (work/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    if result.returncode:
        raise SystemExit(result.returncode)
    print('Passed '+name, flush=True)
def container(image, cwd, command):
    return ['sh', str(root/'dev/run-limited.sh'), 'sudo', '-n', 'podman',
            '--cgroup-manager=cgroupfs', '--events-backend=file', '--storage-driver=vfs',
            '--root', str(root.parent/'.work/podman-root'), '--runroot', str(work/'podman-run'),
            '--tmpdir', str(work/'podman-tmp'), '--transient-store', 'run', '--rm',
            '--cgroups=disabled', '--network=none', '--user', '1000:1000', '-e', 'HOME=/tmp',
            '-e', 'LC_ALL=C.UTF-8', '-e', 'TZ=UTC', '-v', str(workspace)+':/workspace',
            '-w', cwd, image, *command]
run('native-image-check', container(image, '/workspace/distribution', ['make', 'image-check']))
run('container-source-check', container(dev_image, '/workspace',
                                      ['python3', '-B', 'assurance/ci/run-engineering-checks.py', '--mode', 'source']))
run('host-source-check', ['sh', 'dev/run-limited.sh', 'python3', '-B',
                          'assurance/ci/run-engineering-checks.py', '--mode', 'source'])
run('engineering-lint', ['sh', 'dev/run-limited.sh', 'python3', '-B', 'assurance/ci/engineering.py', 'lint'])
assert engineering.source_subject(root) == subject
assert engineering.source_subject(workspace) == subject
for name, expected in inputs.items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest() == expected, name
    assert hashlib.sha256((workspace/name).read_bytes()).hexdigest() == expected, name
report['result'] = 'pass'
report['source_subject_after'] = subject
(work/'report.json').write_text(json.dumps(report, indent=2)+'\n')
print('PASS all checks; exact inputs retained; source subject '+subject, flush=True)
