from pathlib import Path
import subprocess,time,json,os,shutil
work=Path('/evidence');vmwork=work/'vm-package-04';vmwork.mkdir(exist_ok=False)

known=(work/'vm/known_hosts').read_text();(vmwork/'known_hosts').write_text(known)
options=['-F','/dev/null','-o','GSSAPIAuthentication=no','-i','/vm-key','-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','ConnectTimeout=3','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(vmwork/'known_hosts')]
ssh=['/evidence/ssh-wrapper',*options,'-p','22223','builder@127.0.0.1']
args=['qemu-system-x86_64','-machine','q35','-accel','kvm','-cpu','host','-m','2048','-smp','1',
 '-drive','file='+str(work/'vm-package-03/test.qcow2')+',if=virtio,format=qcow2,discard=unmap',
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
  subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223',str(work/'package-input-04.tar'),'builder@127.0.0.1:/tmp/nia-root-reinspection-final.tar'],check=True,timeout=60)
  script='''set -eu
umask 022
mkdir -m 700 /tmp/nia-root-reinspection-final
cd /tmp/nia-root-reinspection-final
tar -xf /tmp/nia-root-reinspection-final.tar
python3 diagnose.py > reproducibility-diagnosis.json
export DEB_BUILD_OPTIONS=parallel=1 TZ=UTC
mkdir build-a build-b
cp -a source build-a/source
cp -a source build-b/source
(cd build-a/source && dpkg-buildpackage -us -uc) > build-a.log 2>&1
(cd build-b/source && dpkg-buildpackage -us -uc) > build-b.log 2>&1
cmp build-a/niaos-root-preparation_0.3.0_amd64.deb build-b/niaos-root-preparation_0.3.0_amd64.deb
cmp build-a/niaos-root-preparation-dbgsym_0.3.0_amd64.deb build-b/niaos-root-preparation-dbgsym_0.3.0_amd64.deb
sha256sum build-a/*.deb build-a/*.dsc build-a/*.tar.xz > package-sha256.txt
sudo dpkg -i build-a/niaos-root-preparation_0.3.0_amd64.deb > install.log 2>&1
cmp tests/root_bank.py /usr/libexec/niaos/root_bank.py
sudo systemd-analyze verify niaos-root-preparation.service niaos-root-preparation.socket var-lib-niaos-roots.mount
if systemctl is-active --quiet niaos-root-preparation.socket; then exit 1; fi
if systemctl is-enabled --quiet niaos-root-preparation.socket; then exit 1; fi
sudo mkdir -m 700 /run/nia-root-extract-test
sudo truncate -s 32M /tmp/nia-root-reinspection-final/disposable.ext4
sudo /sbin/mkfs.ext4 -q -F /tmp/nia-root-reinspection-final/disposable.ext4
sudo mount -o loop,nodev,nosuid,noexec /tmp/nia-root-reinspection-final/disposable.ext4 /run/nia-root-extract-test
sudo chmod 711 /run/nia-root-extract-test
uname -a
dpkg-query -W libarchive13t64 libsodium23
sha256sum /usr/libexec/niaos/root-extract
sudo python3 tests/worker/check_root_extract.py --worker /usr/libexec/niaos/root-extract --target-base /run/nia-root-extract-test --report /tmp/nia-root-reinspection-final/extraction.json
sudo python3 tests/worker/check_root_bank.py --worker /usr/libexec/niaos/root-extract --base /run/nia-root-extract-test --report /tmp/nia-root-reinspection-final/bank.json
sudo python3 tests/worker/check_root_reinspection.py --worker /usr/libexec/niaos/root-extract --base /run/nia-root-extract-test --report /tmp/nia-root-reinspection-final/result.json
sudo umount /run/nia-root-extract-test
'''
  with (vmwork/'worker.log').open('wb') as out:r=subprocess.run(ssh+['sh','-s'],input=script.encode(),stdout=out,stderr=subprocess.STDOUT,timeout=240)
  print('Guest worker test exit',r.returncode,flush=True)
  if r.returncode==0:
   subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223','builder@127.0.0.1:/tmp/nia-root-reinspection-final/result.json',str(vmwork/'result.json')],check=True,timeout=30)
  for name in ['extraction.json','bank.json','build-a.log','build-b.log','package-sha256.txt','install.log','reproducibility-diagnosis.json']:
   subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223','builder@127.0.0.1:/tmp/nia-root-reinspection-final/'+name,str(vmwork/name)],check=False,timeout=30)
  subprocess.run(ssh+['sudo','poweroff'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
  vm.wait(timeout=60)
  (vmwork/'exit.json').write_text(json.dumps(dict(worker_exit=r.returncode,qemu_exit=vm.returncode,base_read_only=True,ram_mib=2048,vcpus=1,network='restricted guest; container loopback SSH only'),indent=2)+'\n')
  if r.returncode:raise SystemExit(r.returncode)
 finally:
  if vm.poll() is None:
   vm.terminate()
   try:vm.wait(timeout=10)
   except subprocess.TimeoutExpired:vm.kill();vm.wait()
