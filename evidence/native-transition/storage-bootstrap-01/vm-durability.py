# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import subprocess,time,json,os,shutil
work=Path('/evidence');vmwork=work/'vm-durability-03';vmwork.mkdir(exist_ok=False)
subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b','/evidence/vm-bootstrap-02/test.qcow2',str(vmwork/'test.qcow2')],check=True)
known=(work/'known_hosts').read_text();(vmwork/'known_hosts').write_text(known)
options=['-F','/dev/null','-o','GSSAPIAuthentication=no','-i','/vm-key','-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','ConnectTimeout=3','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(vmwork/'known_hosts')]
ssh=['/evidence/ssh-wrapper',*options,'-p','22223','builder@127.0.0.1']
args=['qemu-system-x86_64','-machine','q35','-accel','kvm','-cpu','host','-m','2048','-smp','1',
 '-drive','file='+str(vmwork/'test.qcow2')+',if=virtio,format=qcow2,discard=unmap',
 '-netdev','user,id=net0,restrict=on,hostfwd=tcp:127.0.0.1:22223-:22','-device','virtio-net-pci,netdev=net0',
 '-display','none','-serial','file:'+str(vmwork/'serial.log'),'-monitor','none']
with (vmwork/'qemu.log').open('wb') as log:
 vm=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT)
 try:
  deadline=time.monotonic()+180
  while True:
   if vm.poll() is not None:raise RuntimeError('QEMU stopped: '+str(vm.returncode))
   with (vmwork/'ssh-ready.log').open('wb') as ready_log:
    ready=subprocess.run(ssh+['true'],stdout=ready_log,stderr=subprocess.STDOUT,timeout=6)
   if ready.returncode==0:break
   if time.monotonic()>=deadline:raise TimeoutError('guest SSH')
   time.sleep(1)
  print('VM durability readback ready',flush=True)
  subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223',str(work/'check_service_deployment.py'),'builder@127.0.0.1:/var/tmp/nia-service/check_service_deployment.py'],check=True,timeout=30)
  script="""import json,sys
from pathlib import Path
sys.path.insert(0,'/var/tmp/nia-service')
from check_service_deployment import check_bootstrap_after_reboot
p=Path('/var/tmp/nia-service/result.json');r=json.loads(p.read_text())
check_bootstrap_after_reboot(r)
p.write_text(json.dumps(r,indent=2)+'\\n')
for name in ('bootstrap.json','bootstrap-complete.json'):
 source=Path('/var/lib/niaos')/name
 target=Path('/var/tmp/nia-service')/name
 target.write_bytes(source.read_bytes());target.chmod(0o644)
print('bootstrap records and lock inodes survived reboot')
"""
  with (vmwork/'durability.log').open('wb') as out:r=subprocess.run(ssh+['sudo python3 -'],input=script.encode(),stdout=out,stderr=subprocess.STDOUT,timeout=30)
  for name in ('result.json','bootstrap.json','bootstrap-complete.json'):
   subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223','builder@127.0.0.1:/var/tmp/nia-service/'+name,str(vmwork/name)],check=True,timeout=30)
  subprocess.run(ssh+['sudo','poweroff'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
  vm.wait(timeout=60)
  (vmwork/'exit.json').write_text(json.dumps({'readback_exit':r.returncode,'qemu_exit':vm.returncode,'ram_mib':2048,'vcpus':1,'base_read_only':True},indent=2)+'\n')
  if r.returncode:raise SystemExit(r.returncode)
 finally:
  if vm.poll() is None:
   vm.terminate()
   try:vm.wait(timeout=10)
   except subprocess.TimeoutExpired:vm.kill();vm.wait()
