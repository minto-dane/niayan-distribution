# SPDX-License-Identifier: MIT
import os, subprocess
from pathlib import Path
work = Path('/home/nia/devbox/niaos/.work/native-generation-transition-01')
def run(name, args, **env):
    print('Starting ' + name, flush=True)
    with (work / (name + '.log')).open('w') as output:
        subprocess.run(['python3', str(work / 'run-container.py'), *args],
                       env={**os.environ, **env}, stdout=output, stderr=subprocess.STDOUT, check=True)
    print('Passed ' + name, flush=True)
run('accepted-build-test', ['sh', 'pkgcore/ci/test-all.sh'], PROBE_COPY='workspace-independent-long-path', PROBE_MOUNT='/independent-long-workspace')
run('root-probe', ['sh', 'pkgcore/ci/generation-root-refusal-test.sh'], PROBE_COPY='workspace-independent-long-path', PROBE_MOUNT='/independent-long-workspace', PROBE_UID='0:0')
run('sanitized', ['python3', '/evidence/run-sanitized.py'], PROBE_COPY='sanitized')
