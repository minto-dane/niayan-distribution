from pathlib import Path
import subprocess,time,json,os,shutil
work=Path('/evidence');vmwork=work/'vm-bsd-service-01';vmwork.mkdir(exist_ok=False)
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
  subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223',str(work/'runtime.tar'),'builder@127.0.0.1:/var/tmp/nia-service.tar'],check=True,timeout=60)
  script='''set -eu
mkdir -m 711 /var/tmp/nia-service
cd /var/tmp/nia-service
tar -xf /var/tmp/nia-service.tar
export DEB_BUILD_OPTIONS=parallel=1 TZ=UTC
mkdir build-a build-b
cp -a source build-a/source
cp -a source build-b/source
(cd build-a/source && dpkg-buildpackage -us -uc) > build-a.log 2>&1
(cd build-b/source && dpkg-buildpackage -us -uc) > build-b.log 2>&1
cmp build-a/niaos-root-preparation_0.1.0_amd64.deb build-b/niaos-root-preparation_0.1.0_amd64.deb
cmp build-a/niaos-root-preparation-dbgsym_0.1.0_amd64.deb build-b/niaos-root-preparation-dbgsym_0.1.0_amd64.deb
sha256sum build-a/*.deb > package-sha256.txt
sudo dpkg -i build-a/niaos-root-preparation_0.1.0_amd64.deb > install.log 2>&1
sudo systemd-analyze verify niaos-root-preparation.service niaos-root-preparation.socket var-lib-niaos-roots.mount
sudo chown -R root:root runtime
uname -a
sudo python3 check_service_deployment.py --runtime /var/tmp/nia-service/runtime --report /var/tmp/nia-service/result.json
'''
  with (vmwork/'worker.log').open('wb') as out:r=subprocess.run(ssh+['sh','-s'],input=script.encode(),stdout=out,stderr=subprocess.STDOUT,timeout=420)
  print('Guest worker test exit',r.returncode,flush=True)
  if r.returncode==0:
   subprocess.run(ssh+['sudo','reboot'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
   time.sleep(3)
   deadline=time.monotonic()+120
   while True:
    check=subprocess.run(ssh+['systemctl is-active --quiet multi-user.target'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=6)
    if check.returncode==0: break
    if time.monotonic()>deadline: raise TimeoutError('reboot readiness')
    time.sleep(1)
   with (vmwork/'reboot.log').open('wb') as out:
    r=subprocess.run(ssh+['sudo python3 /var/tmp/nia-service/check_service_deployment.py --after-reboot --runtime /var/tmp/nia-service/runtime --report /var/tmp/nia-service/result.json'],stdout=out,stderr=subprocess.STDOUT,timeout=90)
  with (vmwork/'service-journal.log').open('wb') as out:
   subprocess.run(ssh+['sudo journalctl -u niaos-root-preparation.service --no-pager -n 100'],stdout=out,stderr=subprocess.STDOUT,timeout=15)
  with (vmwork/'worker-diagnostics.log').open('wb') as out:
   subprocess.run(ssh+['sudo sh -c \"cat /var/lib/niaos/roots/*/worker.json\"'],stdout=out,stderr=subprocess.STDOUT,timeout=15)
  for report_name in ['result.json','namespace.json','native-service.log','build-a.log','build-b.log','install.log','package-sha256.txt','build-a/niaos-root-preparation_0.1.0_amd64.buildinfo']:
   subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223','builder@127.0.0.1:/var/tmp/nia-service/'+report_name,str(vmwork/Path(report_name).name)],timeout=30)
  if r.returncode==0:
   subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223','builder@127.0.0.1:/var/tmp/nia-service/build-a/niaos-root-preparation_0.1.0_amd64.deb',str(vmwork/'niaos-root-preparation_0.1.0_amd64.deb')],check=True,timeout=30)
  subprocess.run(ssh+['sudo','poweroff'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
  vm.wait(timeout=60)
  (vmwork/'exit.json').write_text(json.dumps(dict(worker_exit=r.returncode,qemu_exit=vm.returncode,base_read_only=True,ram_mib=2048,vcpus=1,network='restricted guest; container loopback SSH only'),indent=2)+'\n')
  if r.returncode:raise SystemExit(r.returncode)
 finally:
  if vm.poll() is None:
   vm.terminate()
   try:vm.wait(timeout=10)
   except subprocess.TimeoutExpired:vm.kill();vm.wait()
