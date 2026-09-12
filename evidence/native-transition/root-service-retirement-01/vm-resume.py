from pathlib import Path
import subprocess,time,json,os,shutil
work=Path('/evidence');vmstate=work/'vm-package-01';vmwork=work/'vm-acceptance-02';vmwork.mkdir(exist_ok=False)
assert (vmstate/'test.qcow2').is_file() and (vmstate/'bank.raw').is_file()
known=(work/'vm/known_hosts').read_text();(vmwork/'known_hosts').write_text(known)
options=['-F','/dev/null','-o','GSSAPIAuthentication=no','-i','/vm-key','-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','ConnectTimeout=3','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(vmwork/'known_hosts')]
ssh=['/evidence/ssh-wrapper',*options,'-p','22223','builder@127.0.0.1']
args=['qemu-system-x86_64','-machine','q35','-accel','kvm','-cpu','host','-m','2048','-smp','1',
 '-drive','file='+str(vmstate/'test.qcow2')+',if=virtio,format=qcow2,discard=unmap',
 '-drive','file='+str(vmstate/'bank.raw')+',if=virtio,format=raw',
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
  subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223',str(work/'runtime.tar'),'builder@127.0.0.1:/home/builder/nia-retirement.tar'],check=True,timeout=60)
  script=(work/'guest-resume.sh').read_text()
  with (vmwork/'worker.log').open('wb') as out:r=subprocess.run(ssh+['sh','-s'],input=script.encode(),stdout=out,stderr=subprocess.STDOUT,timeout=600)
  print('Guest worker test exit',r.returncode,flush=True)
  if r.returncode==0:
   before=subprocess.check_output(ssh+['cat /proc/sys/kernel/random/boot_id'],timeout=6)
   subprocess.run(ssh+['sudo','reboot'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
   time.sleep(3);deadline=time.monotonic()+120
   while True:
    probe=subprocess.run(ssh+['cat /proc/sys/kernel/random/boot_id'],capture_output=True,timeout=6)
    if probe.returncode==0 and probe.stdout!=before:break
    if time.monotonic()>=deadline:raise TimeoutError('reboot readiness')
    time.sleep(1)
   with (vmwork/'reboot.log').open('wb') as out:
    second = "set -eu\ncd /home/builder/nia-retirement\nsudo python3 check_bank_device.py --after-reboot --device /dev/vdb1 --report /home/builder/nia-retirement/bootstrap.json\nsudo python3 check_root_session.py --ending close --report /home/builder/nia-retirement/result.json\n"
    r=subprocess.run(ssh+['sh','-s'],input=second.encode(),stdout=out,stderr=subprocess.STDOUT,timeout=240)
   if r.returncode==0:
    before=subprocess.check_output(ssh+['cat /proc/sys/kernel/random/boot_id'],timeout=6)
    subprocess.run(ssh+['sudo','reboot'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
    time.sleep(3);deadline=time.monotonic()+120
    while True:
     probe=subprocess.run(ssh+['cat /proc/sys/kernel/random/boot_id'],capture_output=True,timeout=6)
     if probe.returncode==0 and probe.stdout!=before:break
     if time.monotonic()>=deadline:raise TimeoutError('second reboot readiness')
     time.sleep(1)
    with (vmwork/'session-reboot.log').open('wb') as out:
     r=subprocess.run(ssh+['sudo python3 /home/builder/nia-retirement/check_root_session.py --after-reboot --report /home/builder/nia-retirement/result.json'],stdout=out,stderr=subprocess.STDOUT,timeout=90)
  with (vmwork/'service-journal.log').open('wb') as out:
   subprocess.run(ssh+['sudo journalctl -u niaos-root-session.service -u niaos-root-bank-check.service -u niaos-root-preparation.service -u var-lib-niaos-roots.mount --no-pager -n 150'],stdout=out,stderr=subprocess.STDOUT,timeout=20)
  for name in ['result.json','bootstrap.json','build-a.log','build-b.log','package-sha256.txt','install.log','install-old.log','purge-old.log','upgrade-live-old.json','upgrade-offline.json','upgrade-live-active.json','bank.json','reinspection.json']:
   subprocess.run(['/evidence/scp-wrapper','-r','-S','/evidence/ssh-wrapper',*options,'-P','22223','builder@127.0.0.1:/home/builder/nia-retirement/'+name,str(vmwork/name)],check=False,timeout=30)
  (vmwork/'packages').mkdir()
  for pattern in ['*.deb','*.dsc','*.tar.xz','*.buildinfo','*.changes']:
   subprocess.run(['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223','builder@127.0.0.1:/home/builder/nia-retirement/build-a/'+pattern,str(vmwork/'packages')],check=True,timeout=30)
  subprocess.run(ssh+['sudo','poweroff'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
  vm.wait(timeout=60)
  (vmwork/'exit.json').write_text(json.dumps(dict(worker_exit=r.returncode,qemu_exit=vm.returncode,base_read_only=True,ram_mib=2048,vcpus=1,network='restricted guest; container loopback SSH only'),indent=2)+'\n')
  if r.returncode:raise SystemExit(r.returncode)
 finally:
  if vm.poll() is None:
   vm.terminate()
   try:vm.wait(timeout=10)
   except subprocess.TimeoutExpired:vm.kill();vm.wait()
