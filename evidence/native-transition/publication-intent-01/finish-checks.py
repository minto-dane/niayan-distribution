# SPDX-License-Identifier: MIT
import os, subprocess
from pathlib import Path
work = Path('/home/nia/devbox/niaos/.work/native-publication-intent-01')
for name, command in [('independent-build', ['make', 'build', 'JOBS=1']), ('independent-test-build', ['make', '-C', 'pkgcore', 'test-build', 'JOBS=1'])]:
    print('Starting ' + name, flush=True)
    with (work / (name + '.log')).open('w') as output:
        subprocess.run(['python3', str(work / 'run-container.py'), *command], stdout=output, stderr=subprocess.STDOUT,
                       env={**os.environ, 'PROBE_COPY': 'workspace-independent-long-path', 'PROBE_MOUNT': '/independent-long-workspace', 'PROBE_TZ': 'Pacific/Honolulu'}, check=True)
    print('Passed ' + name, flush=True)
subprocess.run(['python3', str(work / 'remaining-checks.py')], check=True)
