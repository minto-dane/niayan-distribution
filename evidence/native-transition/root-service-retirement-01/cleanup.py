# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import json,os,shutil,stat
base=Path('/home/nia/devbox/niaos/.work');lab=base/'root-service-retirement-01';old=base/'native-reinspection-transport-01'
assert json.loads((lab/'artifact-check.json').read_text())['result']=='pass'
assert json.loads((lab/'vm-acceptance-02/exit.json').read_text())['qemu_exit']==0
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:args=(proc/'cmdline').read_bytes().split(b'\0')
 except (OSError,PermissionError):continue
 if args and (b'qemu-system' in args[0] or args[0].endswith(b'/podman') or args[0]==b'podman'):
  assert not any(str(lab).encode() in a or str(old).encode() in a for a in args), 'owned runner still active'
# Preserve the meaningful failed execution log before removing its private CAS.
shutil.copy2(lab/'native-check-deadline-01/0.log',lab/'expiry-budget-refusal.log')
for name in ('0.log','1.log','2.log','report.json'):
 p=old/'native-check'/name
 if p.is_file():shutil.copy2(p,old/('completed-native-'+name))
paths=[old/'workspace-01',old/'workspace',old/'native-check',
 lab/'native-check-deadline-01',lab/'native-check/archive',lab/'native-check/configured',lab/'native-check/stage',
 lab/'root-refusal',lab/'generations-final/v5',lab/'generations-final/v6',lab/'generations-final/v6-media-refused',
 lab/'vm-package-01/test.qcow2',lab/'vm-package-01/bank.raw',lab/'vm-unstarted-01',lab/'vm-kvm-refused-01']
rows=[]
for path in paths:
 assert path.parent.resolve().is_relative_to(base) and not path.is_symlink(),str(path)
 if not path.exists():continue
 files=[path]
 if path.is_dir():
  files += [Path(parent)/n for parent,dirs,names in os.walk(path,followlinks=False) for n in dirs+names]
 logical=allocated=0
 for entry in files:
  info=entry.lstat()
  logical+=info.st_size;allocated+=info.st_blocks*512
 rows.append(dict(path=str(path),logical_bytes=logical,allocated_bytes=allocated))
 if path.is_dir():shutil.rmtree(path)
 else:path.unlink()
 assert not path.exists()
result=dict(result='pass',deleted=rows,allocated_bytes=sum(r['allocated_bytes'] for r in rows),
 retained_current_build=True,retained_package_and_source=True,shared_builder_and_images_untouched=True,
 unrelated_processes_stopped=False,host_device_permissions_changed=False)
(lab/'cleanup.json').write_text(json.dumps(result,indent=2)+'\n');os.chown(lab/'cleanup.json',1000,1000)
os.chmod(lab/'cleanup.json',0o644)
(old/'RETIRED.txt').write_text('Superseded by ../root-service-retirement-01. Obsolete build and CAS caches removed; logs and source manifests retained.\n')
os.chown(old/'RETIRED.txt',1000,1000)
print('PASS removed allocated bytes',result['allocated_bytes'])
