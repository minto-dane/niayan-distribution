from pathlib import Path
import subprocess,time,json,os,shutil
work=Path('/evidence');vmwork=work/'vm-preparation-02';vmwork.mkdir(exist_ok=False)
subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b','/vm-base/builder.qcow2',str(vmwork/'test.qcow2')],check=True)
known=(work/'vm-02/known_hosts').read_text();(vmwork/'known_hosts').write_text(known)
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
  print('VM SSH ready',flush=True)
  subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223',str(work/'runtime.tar'),'builder@127.0.0.1:/tmp/nia-root-extract.tar'],check=True,timeout=60)
  script='''set -eu
mkdir -m 700 /tmp/nia-root-extract
cd /tmp/nia-root-extract
tar -xf /tmp/nia-root-extract.tar
cat > worker <<'WRAPPER'
#!/bin/sh
exec /tmp/nia-root-extract/lib/ld-linux-x86-64.so.2 --library-path /tmp/nia-root-extract/lib /tmp/nia-root-extract/build/root-extract "$@"
WRAPPER
chmod 700 worker
sudo chown -R root:root /tmp/nia-root-extract
sudo chmod 711 /tmp/nia-root-extract
sudo mkdir -m 700 /run/nia-root-extract-test
sudo truncate -s 32M /tmp/nia-root-extract/disposable.ext4
sudo /sbin/mkfs.ext4 -q -F /tmp/nia-root-extract/disposable.ext4
sudo mount -o loop,nodev,nosuid,noexec /tmp/nia-root-extract/disposable.ext4 /run/nia-root-extract-test
sudo chmod 711 /run/nia-root-extract-test
uname -a
findmnt -T /run/nia-root-extract-test -o TARGET,FSTYPE,OPTIONS
sudo python3 native/worker/check_root_preparation.py --configured --worker /tmp/nia-root-extract/worker --driver /tmp/nia-root-extract/build/driver --loader /tmp/nia-root-extract/lib/ld-linux-x86-64.so.2 --libraries /tmp/nia-root-extract/lib --fixtures /tmp/nia-root-extract/fixtures --base /run/nia-root-extract-test --report /tmp/nia-root-extract/result.json
sudo umount /run/nia-root-extract-test
'''
  with (vmwork/'worker.log').open('wb') as out:r=subprocess.run(ssh+['sh','-s'],input=script.encode(),stdout=out,stderr=subprocess.STDOUT,timeout=240)
  print('Guest worker test exit',r.returncode,flush=True)
  if r.returncode==0:
   subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223','builder@127.0.0.1:/tmp/nia-root-extract/result.json',str(vmwork/'result.json')],check=True,timeout=30)
  for name in ['native-prepare.log','native-deny-post.log']:
   subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223','builder@127.0.0.1:/tmp/nia-root-extract/'+name,str(vmwork/name)],check=False,timeout=30)
  subprocess.run(ssh+['sudo','poweroff'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
  vm.wait(timeout=60)
  (vmwork/'exit.json').write_text(json.dumps(dict(worker_exit=r.returncode,qemu_exit=vm.returncode,base_read_only=True,ram_mib=2048,vcpus=1,network='restricted guest; container loopback SSH only'),indent=2)+'\n')
  if r.returncode:raise SystemExit(r.returncode)
 finally:
  if vm.poll() is None:
   vm.terminate()
   try:vm.wait(timeout=10)
   except subprocess.TimeoutExpired:vm.kill();vm.wait()
