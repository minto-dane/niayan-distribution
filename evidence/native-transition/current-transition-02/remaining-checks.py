# SPDX-License-Identifier: MIT
import os, subprocess
from pathlib import Path
root = Path('/home/nia/devbox/niaos/nia-os-consent')
work = root.parent / '.work/current-transition-qualification-02'
def run(name, command, **env):
    print('Starting ' + name, flush=True)
    with (work / (name + '.log')).open('w') as output:
        subprocess.run(command, cwd=root, env={**os.environ, **env}, stdout=output, stderr=subprocess.STDOUT, check=True)
    print('Passed ' + name, flush=True)
common = ['python3', str(work / 'run-container.py')]
env = dict(PROBE_COPY='workspace-independent-long-path', PROBE_MOUNT='/independent-long-workspace', PROBE_TZ='Pacific/Honolulu')
run('independent-build', common + ['make', 'build', 'JOBS=1'], **env)
run('independent-test-build', common + ['make', '-C', 'pkgcore', 'test-build', 'JOBS=1'], **env)
run('build-comparison', ['python3', str(work / 'compare-builds.py')])
run('workspace-build-comparison', ['python3', str(work / 'compare-workspaces.py')])
run('source-check', ['sh', 'dev/run-limited.sh', 'python3', 'assurance/ci/run-engineering-checks.py', '--mode', 'source'])
