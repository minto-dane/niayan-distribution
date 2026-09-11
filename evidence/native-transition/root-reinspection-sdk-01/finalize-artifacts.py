# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import hashlib,json,os,stat,tarfile
lab=Path(__file__).resolve().parent;root=Path('/home/nia/devbox/niaos/nia-os-consent')
inputs=json.loads((lab/'runtime-inputs.json').read_text())
with tarfile.open(lab/'runtime.tar') as tar:
 for name,digest in inputs['drivers'].items():
  raw=tar.extractfile('build/'+name).read();assert hashlib.sha256(raw).hexdigest()==digest
  assert raw==(lab/'workspace/pkgcore/build/test-bin'/name).read_bytes()
 for name in ['root_bank.py','worker/check_root_preparation.py','worker/check_root_reinspection.py','worker/check_root_extract.py']:
  assert tar.extractfile('native/'+name).read()==(root/'distribution/native'/name).read_bytes()
 assert hashlib.sha256(tar.extractfile('service.deb').read()).hexdigest()==inputs['service_deb']
assert inputs['service_deb']=='57733331e9453dde91b9b2e4d667efde7ebca201f73bc856591bf946dd44629f'
for name in ['configured','plain']:
 report=json.loads((lab/'vm-sdk-02'/name/'result.json').read_text())
 assert report['result']=='pass' and report['native_reinspection'] and report['response_before_fd_close_delay_ms']==100
 assert report['cases'][0]['bank']['worker_sha256']=='b55000d2e21d96c8e75a9f36dda4bbcf5c77c9dbf42074fa39b1600b1c113322'
(lab/'artifact-check.json').write_text(json.dumps(dict(result='pass',packaged_drivers_and_tools_equal_current=True,unchanged_service_version='0.3.0',service_deb_sha256=inputs['service_deb'],worker_sha256=report['cases'][0]['bank']['worker_sha256']),indent=2)+'\n')
active=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  if (p/'comm').read_text().strip().startswith('qemu-system'):active.append(p.name)
 except (FileNotFoundError,PermissionError):pass
assert not active,active
removed=[]
for name in ['vm-sdk-01','vm-sdk-02']:
 assert json.loads((lab/name/'exit.json').read_text())['qemu_exit']==0
 path=lab/name/'test.qcow2';info=path.lstat()
 assert stat.S_ISREG(info.st_mode) and info.st_nlink==1 and not path.parent.is_symlink()
 removed.append(dict(path=str(path.relative_to(lab)),allocated_bytes=info.st_blocks*512,logical_bytes=info.st_size))
for item in removed:(lab/item['path']).unlink()
(lab/'storage-cleanup.json').write_text(json.dumps(dict(removed=removed,allocated_bytes_removed=sum(i['allocated_bytes'] for i in removed),visible_qemu_processes=active,full_host_fd_audit=False,base_and_accepted_vms_untouched=True,source_and_final_sdk_build_retained=True),indent=2)+'\n')
print('PASS exact runtime artifacts; removed two completed disposable VM overlays')
