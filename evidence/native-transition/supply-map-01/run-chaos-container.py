# SPDX-License-Identifier: MIT
import os
from pathlib import Path
import subprocess
import sys
root=Path('/home/nia/devbox/niaos/nia-os-consent');work=Path(__file__).resolve().parent
image=os.environ.get('PROBE_IMAGE') or (work/'dev-image.id').read_text().strip()
workspace=work/os.environ.get('PROBE_TREE','workspace')
mount=os.environ.get('PROBE_MOUNT','/workspace')
args=['sh',str(root/'dev/run-limited.sh'),'sudo','-n','podman','--cgroup-manager=cgroupfs','--events-backend=file','--storage-driver=vfs',
      '--root',str(root.parent/'.work/podman-root'),'--runroot',str(work/'podman-run'),'--tmpdir',str(work/'podman-tmp'),'--transient-store',
      'run','--rm','--cgroups=disabled','--network=none','--cap-add=SYS_PTRACE','--cap-add=DAC_READ_SEARCH','--user',os.environ.get('PROBE_UID','1000:1000'),'-e','HOME=/tmp',
      '-e','LC_ALL=C.UTF-8','-e','TZ='+os.environ.get('PROBE_TZ','UTC'),'-v',str(workspace)+':'+mount,'-v',str(work)+':/evidence',
      '-w',os.environ.get('PROBE_CWD',mount)]
if os.environ.get('PROBE_SOURCE_EPOCH'):
    args+=['-e','SOURCE_DATE_EPOCH='+os.environ['PROBE_SOURCE_EPOCH']]
args.append(image)
raise SystemExit(subprocess.call(args+sys.argv[1:]))
