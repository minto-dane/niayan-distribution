# SPDX-License-Identifier: BSD-3-Clause
import json,os,signal,shutil,subprocess,time
from pathlib import Path
p=Path(__file__).resolve().parent
args=['podman','--cgroup-manager=cgroupfs','--events-backend=file','--storage-driver=vfs','--root',str(p.parent/'podman-root'),'--runroot',str(p/'podman-run'),'--tmpdir',str(p/'podman-tmp'),'--transient-store','build','--isolation=chroot','--network=host','--layers=false','--iidfile',str(p/'new-dev-image.id'),'-f',str(p/'build-context/dev/Containerfile'),str(p/'build-context')]
started=time.monotonic(); minimum=shutil.disk_usage(p).free;reason=None
with subprocess.Popen(args,start_new_session=True) as child:
 try:
  while child.poll() is None:
   minimum=min(minimum,shutil.disk_usage(p).free)
   if minimum < 3*1024**3: raise RuntimeError('disk reserve below 3 GiB')
   if time.monotonic()-started > 900: raise RuntimeError('build time budget exhausted')
   time.sleep(1)
 except BaseException as error:
  reason=repr(error)
  try:os.killpg(child.pid,signal.SIGTERM)
  except ProcessLookupError:pass
  try:child.wait(timeout=10)
  except subprocess.TimeoutExpired:
   os.killpg(child.pid,signal.SIGKILL);child.wait()
report=dict(result='pass' if child.returncode==0 and reason is None else 'fail',exit_code=child.returncode,reason=reason,minimum_free_bytes=minimum,elapsed_seconds=time.monotonic()-started,command=args)
(p/'image-build-report.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['result']=='pass' else 1)
