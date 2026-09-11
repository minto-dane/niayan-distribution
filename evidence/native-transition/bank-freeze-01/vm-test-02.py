from pathlib import Path
import subprocess,time,json,os,shutil
work=Path('/evidence');vmwork=work/'vm-test-02';vmwork.mkdir(exist_ok=False)
known=(work/'vm/known_hosts').read_text();(vmwork/'known_hosts').write_text(known)
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
  subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223',str(work/'package-input-02.tar'),'builder@127.0.0.1:/home/builder/nia-bank-freeze-02.tar'],check=True,timeout=60)
  script='''set -eu
umask 022
mkdir -m 700 /home/builder/nia-bank-freeze-02
cd /home/builder/nia-bank-freeze-02
tar -xf /home/builder/nia-bank-freeze-02.tar
sudo dpkg -i service.deb > install.log 2>&1
sudo mkdir -m 700 /run/nia-old-freeze-bank
sudo mount -o loop,ro,nodev,nosuid,noexec /home/builder/nia-bank-freeze-01/freeze.ext4 /run/nia-old-freeze-bank
sudo python3 - <<'DIAG' > initial-atime-diagnosis.json
import json,os
p='/run/nia-old-freeze-bank/'+'1'*32+'/root/etc/value'
s=os.stat(p)
print(json.dumps(dict(actual_atime_ns=s.st_atime_ns,expected_atime_ns=1700000001000000009,actual_mtime_ns=s.st_mtime_ns,expected_mtime_ns=1700000000000000007),indent=2))
assert s.st_atime_ns!=1700000001000000009 and s.st_mtime_ns==1700000000000000007
DIAG
sudo umount /run/nia-old-freeze-bank
cmp tests/root_bank.py /usr/libexec/niaos/root_bank.py
cmp tests/root_freeze.py /usr/libexec/niaos/root_freeze.py
sudo systemd-analyze verify niaos-root-preparation.service niaos-root-preparation.socket var-lib-niaos-roots.mount
if systemctl is-active --quiet niaos-root-preparation.socket; then exit 1; fi
if systemctl is-enabled --quiet niaos-root-preparation.socket; then exit 1; fi
sudo mkdir -m 700 /run/nia-root-extract-test
sudo truncate -s 32M /home/builder/nia-bank-freeze-02/disposable.ext4
sudo /sbin/mkfs.ext4 -q -F /home/builder/nia-bank-freeze-02/disposable.ext4
sudo mount -o loop,nodev,nosuid,noexec /home/builder/nia-bank-freeze-02/disposable.ext4 /run/nia-root-extract-test
sudo chmod 711 /run/nia-root-extract-test
uname -a
dpkg-query -W libarchive13t64 libsodium23
sha256sum /usr/libexec/niaos/root-extract
mkdir freeze configured plain
sudo mkdir -m 700 /run/nia-freeze-bank-test
sudo truncate -s 32M /home/builder/nia-bank-freeze-02/freeze.ext4
sudo /sbin/mkfs.ext4 -q -F /home/builder/nia-bank-freeze-02/freeze.ext4
sudo mount -o loop,nodev,nosuid,noexec /home/builder/nia-bank-freeze-02/freeze.ext4 /run/nia-freeze-bank-test
sudo rmdir /run/nia-freeze-bank-test/lost+found
sudo chmod 700 /run/nia-freeze-bank-test
sudo python3 tests/worker/check_root_freeze.py --worker /usr/libexec/niaos/root-extract --bank /run/nia-freeze-bank-test --report /home/builder/nia-bank-freeze-02/freeze/result.json
sudo umount /run/nia-freeze-bank-test
sudo python3 tests/worker/check_root_bank.py --worker /usr/libexec/niaos/root-extract --base /run/nia-root-extract-test --report /home/builder/nia-bank-freeze-02/bank.json
sudo python3 tests/worker/check_root_preparation.py --reinspect --freeze-bank --configured --worker /usr/libexec/niaos/root-extract --driver /home/builder/nia-bank-freeze-02/drivers/run_root_configuration_tests --loader /home/builder/nia-bank-freeze-02/lib/ld-linux-x86-64.so.2 --libraries /home/builder/nia-bank-freeze-02/lib --fixtures /home/builder/nia-bank-freeze-02/fixtures-configured --base /run/nia-root-extract-test --report /home/builder/nia-bank-freeze-02/configured/result.json
sudo python3 tests/worker/check_root_preparation.py --reinspect --freeze-bank --worker /usr/libexec/niaos/root-extract --driver /home/builder/nia-bank-freeze-02/drivers/run_root_archive_tests --loader /home/builder/nia-bank-freeze-02/lib/ld-linux-x86-64.so.2 --libraries /home/builder/nia-bank-freeze-02/lib --fixtures /home/builder/nia-bank-freeze-02/fixtures-plain --base /run/nia-root-extract-test --report /home/builder/nia-bank-freeze-02/plain/result.json
sudo umount /run/nia-root-extract-test
'''
  with (vmwork/'worker.log').open('wb') as out:r=subprocess.run(ssh+['sh','-s'],input=script.encode(),stdout=out,stderr=subprocess.STDOUT,timeout=240)
  print('Guest worker test exit',r.returncode,flush=True)
  for name in ['freeze','configured','plain','bank.json','install.log','initial-atime-diagnosis.json']:
   subprocess.run(['/evidence/scp-wrapper','-r','-S','/evidence/ssh-wrapper',*options,'-P','22223','builder@127.0.0.1:/home/builder/nia-bank-freeze-02/'+name,str(vmwork/name)],check=False,timeout=30)
  subprocess.run(ssh+['sudo','poweroff'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
  vm.wait(timeout=60)
  (vmwork/'exit.json').write_text(json.dumps(dict(worker_exit=r.returncode,qemu_exit=vm.returncode,base_read_only=True,ram_mib=2048,vcpus=1,network='restricted guest; container loopback SSH only'),indent=2)+'\n')
  if r.returncode:raise SystemExit(r.returncode)
 finally:
  if vm.poll() is None:
   vm.terminate()
   try:vm.wait(timeout=10)
   except subprocess.TimeoutExpired:vm.kill();vm.wait()
