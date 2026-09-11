from pathlib import Path
import subprocess,time,json,os,shutil
work=Path('/evidence');vmwork=work/'vm-artifacts-06';vmwork.mkdir(exist_ok=False)
known=(work/'vm/known_hosts').read_text();(vmwork/'known_hosts').write_text(known)
options=['-F','/dev/null','-o','GSSAPIAuthentication=no','-i','/vm-key','-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','ConnectTimeout=3','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(vmwork/'known_hosts')]
ssh=['/evidence/ssh-wrapper',*options,'-p','22223','builder@127.0.0.1']
args=['qemu-system-x86_64','-machine','q35','-accel','kvm','-cpu','host','-m','2048','-smp','1',
 '-drive','file='+str(work/'vm-package-05/test.qcow2')+',if=virtio,format=qcow2,discard=unmap',
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
  print('VM SSH ready',flush=True)
  script='''set -eu
cd /home/builder/nia-root-reinspection-05
sha256sum build-b/*.deb build-b/*.dsc build-b/*.tar.xz > build-b-sha256.txt
dpkg-query -W > installed-packages.txt
'''
  with (vmwork/'worker.log').open('wb') as out:r=subprocess.run(ssh+['sh','-s'],input=script.encode(),stdout=out,stderr=subprocess.STDOUT,timeout=240)
  print('Guest worker test exit',r.returncode,flush=True)
  if r.returncode==0:
   for name in ['build-a/niaos-root-preparation_0.3.0_amd64.buildinfo','build-a/niaos-root-preparation_0.3.0_amd64.changes','build-b/niaos-root-preparation_0.3.0_amd64.buildinfo','build-b/niaos-root-preparation_0.3.0_amd64.changes','build-b-sha256.txt','installed-packages.txt']:
    target=vmwork/name;target.parent.mkdir(exist_ok=True)
    subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223','builder@127.0.0.1:/home/builder/nia-root-reinspection-05/'+name,str(target)],check=True,timeout=30)
  subprocess.run(ssh+['sudo','poweroff'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
  vm.wait(timeout=60)
  (vmwork/'exit.json').write_text(json.dumps(dict(worker_exit=r.returncode,qemu_exit=vm.returncode,base_read_only=True,ram_mib=2048,vcpus=1,network='restricted guest; container loopback SSH only'),indent=2)+'\n')
  if r.returncode:raise SystemExit(r.returncode)
 finally:
  if vm.poll() is None:
   vm.terminate()
   try:vm.wait(timeout=10)
   except subprocess.TimeoutExpired:vm.kill();vm.wait()
