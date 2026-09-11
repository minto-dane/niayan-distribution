from pathlib import Path
import subprocess,time,json,os,shutil
work=Path('/evidence');vmwork=work/'vm-test-04';vmwork.mkdir(exist_ok=False)
subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b','/vm-base/builder.qcow2',str(vmwork/'test.qcow2')],check=True)
subprocess.run(['qemu-img','create','-f','raw',str(vmwork/'bank.raw'),'64M'],check=True)
known=(work/'vm/known_hosts').read_text();(vmwork/'known_hosts').write_text(known)
options=['-F','/dev/null','-o','GSSAPIAuthentication=no','-i','/vm-key','-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','ConnectTimeout=3','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(vmwork/'known_hosts')]
ssh=['/evidence/ssh-wrapper',*options,'-p','22223','builder@127.0.0.1']
args=['qemu-system-x86_64','-machine','q35','-accel','kvm','-cpu','host','-m','2048','-smp','1',
 '-drive','file='+str(vmwork/'test.qcow2')+',if=virtio,format=qcow2,discard=unmap',
 '-drive','file='+str(vmwork/'bank.raw')+',if=virtio,format=raw',
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
  subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223',str(work/'runtime-03.tar'),'builder@127.0.0.1:/home/builder/nia-root-session-04.tar'],check=True,timeout=60)
  script='''set -eu
umask 022
mkdir -m 700 /home/builder/nia-root-session-04
cd /home/builder/nia-root-session-04
tar -xf /home/builder/nia-root-session-04.tar
sudo dpkg -i dependencies/*.deb component.deb service.deb > install.log 2>&1
sudo systemd-analyze verify niaos-root-preparation.service niaos-root-preparation.socket niaos-root-bank-check.service niaos-root-session.socket niaos-root-session.service var-lib-niaos-roots.mount
if systemctl is-active --quiet niaos-root-preparation.socket; then exit 1; fi
if systemctl is-enabled --quiet niaos-root-preparation.socket; then exit 1; fi
# Only the additional private 64 MiB VM disk is formatted by this fixture.
test "$(sudo blockdev --getsize64 /dev/vdb)" = 67108864
printf 'label: gpt\n, , L\n' | sudo sfdisk /dev/vdb
sudo udevadm settle
sudo mkfs.ext4 -q /dev/vdb1
uname -a
sha256sum /usr/libexec/niaos/root-extract /usr/libexec/nia/pkg_store_bootstrap
sudo python3 check_bank_device.py --device /dev/vdb1 --report /home/builder/nia-root-session-04/bootstrap.json
sudo python3 check_root_session.py --ending disconnect --report /home/builder/nia-root-session-04/result.json
'''
  with (vmwork/'worker.log').open('wb') as out:r=subprocess.run(ssh+['sh','-s'],input=script.encode(),stdout=out,stderr=subprocess.STDOUT,timeout=240)
  print('Guest worker test exit',r.returncode,flush=True)
  with (vmwork/'service-journal.log').open('wb') as out:
   subprocess.run(ssh+['sudo journalctl -u niaos-root-session.service -u niaos-root-bank-check.service -u niaos-root-preparation.service -u var-lib-niaos-roots.mount --no-pager -n 150'],stdout=out,stderr=subprocess.STDOUT,timeout=20)
  for name in ['result.json','bootstrap.json','install.log']:
   subprocess.run(['/evidence/scp-wrapper','-r','-S','/evidence/ssh-wrapper',*options,'-P','22223','builder@127.0.0.1:/home/builder/nia-root-session-04/'+name,str(vmwork/name)],check=False,timeout=30)
  subprocess.run(ssh+['sudo','poweroff'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
  vm.wait(timeout=60)
  (vmwork/'exit.json').write_text(json.dumps(dict(worker_exit=r.returncode,qemu_exit=vm.returncode,base_read_only=True,ram_mib=2048,vcpus=1,network='restricted guest; container loopback SSH only'),indent=2)+'\n')
  if r.returncode:raise SystemExit(r.returncode)
 finally:
  if vm.poll() is None:
   vm.terminate()
   try:vm.wait(timeout=10)
   except subprocess.TimeoutExpired:vm.kill();vm.wait()
