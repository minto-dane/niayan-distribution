# SPDX-License-Identifier: MIT
import json, os, subprocess
from pathlib import Path
work = Path('/home/nia/devbox/niaos/.work/native-generation-transition-01')
def run(name, args):
    print('Starting ' + name, flush=True)
    with (work / (name + '.log')).open('w') as output:
        subprocess.run(['python3', str(work / 'run-container.py'), *args],
                       env={**os.environ, 'PROBE_COPY': 'workspace'},
                       stdout=output, stderr=subprocess.STDOUT, check=True)
available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
(work / 'memory-before-first-build.json').write_text(json.dumps({'available_bytes': available, 'guard_start_required_bytes': 4096 * 1024 * 1024}, indent=2) + '\n')
if available >= 4352 * 1024 * 1024:
    # Preserve the failed attempt and run the unchanged complete gate only when
    # its real host prerequisite has recovered, with a small extra margin.
    run('workspace-recheck', ['make', 'check', 'private-dbus', 'JOBS=1'])
else:
    # Ordinary bounded compilation is independently useful. This does not mark
    # the failed complete source/Ada gate as passing or execute any prover.
    run('workspace-build', ['env', '-u', 'TZ', '-u', 'SOURCE_DATE_EPOCH', 'make', 'build', 'JOBS=1'])
    run('workspace-test-build', ['env', '-u', 'TZ', '-u', 'SOURCE_DATE_EPOCH', 'make', '-C', 'pkgcore', 'test-build', 'JOBS=1'])
    run('private-dbus', ['make', 'private-dbus', 'JOBS=1'])
print('First build sequence completed; inspect whole-gate reports separately.', flush=True)
