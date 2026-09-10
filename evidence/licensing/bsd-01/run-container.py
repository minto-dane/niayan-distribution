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
      'run','--rm','--cgroups=disabled','--network=none','--user',os.environ.get('PROBE_UID','1000:1000'),'-e','HOME=/tmp',
      '-e','LC_ALL=C.UTF-8','-e','TZ='+os.environ.get('PROBE_TZ','UTC'),'-v',str(workspace)+':'+mount,'-v',str(work)+':/evidence',
      '-w',os.environ.get('PROBE_CWD',mount)]
if os.environ.get('PROBE_SOURCE_EPOCH'):
    args+=['-e','SOURCE_DATE_EPOCH='+os.environ['PROBE_SOURCE_EPOCH']]
if os.environ.get('PROBE_TMPFS'):
    args += ['--cap-add', 'MKNOD', '--tmpfs', '/materialize:rw,nodev,nosuid,noexec,size=32m,mode=0700']
if os.environ.get('PROBE_VM'):
    args += ['--device', '/dev/kvm', '-v', str(work.parent/'distro-builder-vm')+':/vm-base:ro', '-v', str(work.parent/'distro-builder-vm/ssh-key')+':/vm-key:ro']
args.append(image)
raise SystemExit(subprocess.call(args+sys.argv[1:]))
