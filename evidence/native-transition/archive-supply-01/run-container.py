# SPDX-License-Identifier: MIT
import os, subprocess, sys
from pathlib import Path
root=Path('/home/nia/devbox/niaos/nia-os-consent');work=root.parent/'.work/native-archive-supply-01'
image=(work/'native-image.id').read_text().strip() if os.environ.get('PROBE_IMAGE')=='native' else '0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a'
args=['sh',str(root/'dev/run-limited.sh'),'sudo','-n','podman','--cgroup-manager=cgroupfs','--events-backend=file','--storage-driver=vfs',
      '--root',str(root.parent/'.work/podman-root'),'--runroot',str(work/'podman-run'),'--tmpdir',str(work/'podman-tmp'),'--transient-store',
      'run','--rm','--cgroups=disabled','--network=none','--user',os.environ.get('PROBE_UID','1000:1000'),'-e','HOME=/tmp',
      '-e','LC_ALL=C.UTF-8','-e','TZ=UTC','-v',str(work/'workspace')+':/workspace','-v',str(work)+':/evidence',
      '-v',str(work/'official')+':/official:ro','-w',os.environ.get('PROBE_CWD','/workspace'),image]
raise SystemExit(subprocess.call(args+sys.argv[1:]))
