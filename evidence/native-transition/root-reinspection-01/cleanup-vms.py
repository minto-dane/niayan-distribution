# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import json,os,stat
lab=Path('/home/nia/devbox/niaos/.work/native-root-reinspection-01')
active=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  if (p/'comm').read_text().strip().startswith('qemu-system'):active.append(p.name)
 except (FileNotFoundError,PermissionError):pass
assert not active,active
assert json.loads((lab/'artifact-verification.json').read_text())['result']=='pass'
assert json.loads((lab/'vm-artifacts-06/exit.json').read_text())['qemu_exit']==0
items=[];before=os.statvfs(lab)
for name in ['vm-reinspection-01/test.qcow2','vm-reinspection-02/test.qcow2','vm-package-03/test.qcow2','vm-package-05/test.qcow2']:
 path=lab/name;info=path.lstat()
 assert not path.parent.is_symlink() and stat.S_ISREG(info.st_mode) and info.st_nlink==1
 items.append(dict(path=name,logical_bytes=info.st_size,allocated_bytes=info.st_blocks*512,reason='completed private disposable VM overlay; source, packages and reports retained'))
for item in items:(lab/item['path']).unlink()
after=os.statvfs(lab)
(lab/'storage-cleanup.json').write_text(json.dumps(dict(removed=items,allocated_bytes_removed=sum(i['allocated_bytes'] for i in items),free_bytes_before=before.f_bavail*before.f_frsize,free_bytes_after=after.f_bavail*after.f_frsize,visible_qemu_processes=active,full_host_fd_audit=False,base_and_accepted_vms_untouched=True),indent=2)+'\n')
print('Removed',len(items),'completed private VM overlays;',sum(i['allocated_bytes'] for i in items),'allocated bytes')
