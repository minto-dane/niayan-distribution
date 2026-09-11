from pathlib import Path
import subprocess,time,json,os,shutil
work=Path('/evidence');vmwork=work/'vm-entry-03';vmwork.mkdir(exist_ok=False)
# Reopen only the previously created disposable overlay; package bytes are unchanged.
known=(work/'vm-02/known_hosts').read_text();(vmwork/'known_hosts').write_text(known)
options=['-F','/dev/null','-o','GSSAPIAuthentication=no','-i','/vm-key','-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','ConnectTimeout=3','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(vmwork/'known_hosts')]
ssh=['/evidence/ssh-wrapper',*options,'-p','22223','builder@127.0.0.1']
args=['qemu-system-x86_64','-machine','q35','-accel','kvm','-cpu','host','-m','2048','-smp','1',
 '-drive','file='+str(work/'vm-package-01/test.qcow2')+',if=virtio,format=qcow2,discard=unmap',
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
  subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223',str(work/'package-input.tar'),'builder@127.0.0.1:/tmp/nia-root-package.tar'],check=True,timeout=60)
  script='set -eu\nmkdir -m 700 /tmp/nia-root-package\ncd /tmp/nia-root-package\ntar -xf /tmp/nia-root-package.tar\nsha256sum /usr/libexec/niaos/root-extract\ntruncate -s 32M /tmp/nia-root-package/disposable.ext4\nsudo /sbin/mkfs.ext4 -q -F /tmp/nia-root-package/disposable.ext4\nsudo mkdir -m 700 /run/nia-root-extract-test\nsudo mount -o loop,nodev,nosuid,noexec /tmp/nia-root-package/disposable.ext4 /run/nia-root-extract-test\nsudo chmod 700 /run/nia-root-extract-test\nsudo python3 check_configuration_entry.py --inputs /tmp/nia-root-package/inputs --worker /usr/libexec/niaos/root-extract --target-base /run/nia-root-extract-test --report /tmp/nia-root-package/configuration-result.json\nsudo umount /run/nia-root-extract-test\n'
  with (vmwork/'worker.log').open('wb') as out:r=subprocess.run(ssh+['sh','-s'],input=script.encode(),stdout=out,stderr=subprocess.STDOUT,timeout=420)
  print('Guest worker test exit',r.returncode,flush=True)
  for name in ['configuration-result.json']:
   subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223','builder@127.0.0.1:/tmp/nia-root-package/'+name,str(vmwork/Path(name).name)],check=False,timeout=30)
  subprocess.run(ssh+['sudo','poweroff'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
  vm.wait(timeout=60)
  (vmwork/'exit.json').write_text(json.dumps(dict(worker_exit=r.returncode,qemu_exit=vm.returncode,base_read_only=True,ram_mib=2048,vcpus=1,network='restricted guest; container loopback SSH only'),indent=2)+'\n')
  if r.returncode:raise SystemExit(r.returncode)
 finally:
  if vm.poll() is None:
   vm.terminate()
   try:vm.wait(timeout=10)
   except subprocess.TimeoutExpired:vm.kill();vm.wait()
