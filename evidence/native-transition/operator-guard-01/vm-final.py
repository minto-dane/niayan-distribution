# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import json
import subprocess
import time

lab = Path('/evidence')
work = lab/'vm-final'
work.mkdir(exist_ok=False)
subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b','/vm-base/builder.qcow2',str(work/'system.qcow2')],check=True)
options=['-F','/dev/null','-o','GSSAPIAuthentication=no','-i','/vm-key','-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','ConnectTimeout=3','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile=/evidence/known_hosts']
ssh=['/evidence/ssh-wrapper',*options,'-p','22223','builder@127.0.0.1']
scp=['/evidence/scp-wrapper','-S','/evidence/ssh-wrapper',*options,'-P','22223']
args=['qemu-system-x86_64','-machine','q35','-accel','kvm','-cpu','host','-m','2048','-smp','1',
      '-drive','file='+str(work/'system.qcow2')+',if=virtio,format=qcow2,discard=unmap',
      '-netdev','user,id=net0,restrict=on,hostfwd=tcp:127.0.0.1:22223-:22',
      '-device','virtio-net-pci,netdev=net0','-display','none',
      '-serial','file:'+str(work/'serial.log'),'-monitor','none']
with (work/'qemu.log').open('wb') as log:
    vm=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT)
    try:
        for _ in range(90):
            if vm.poll() is not None:raise RuntimeError('VM exited')
            ready=subprocess.run(ssh+['true'],capture_output=True,timeout=6)
            if ready.returncode==0:break
            time.sleep(1)
        else:raise TimeoutError('VM startup')
        print('VM ready',flush=True)
        subprocess.run(scp+[str(lab/'runtime-final.tar'),'builder@127.0.0.1:/home/builder/runtime.tar'],check=True,timeout=60)
        with (work/'guest.log').open('wb') as out:
            result=subprocess.run(ssh+['sh','-s'],input=(lab/'guest-final.sh').read_bytes(),stdout=out,stderr=subprocess.STDOUT,timeout=420)
        print('Guest result',result.returncode,flush=True)
        with (work/'journal.log').open('wb') as out:
            subprocess.run(ssh+['sudo journalctl -u niaos-root-session.service --no-pager -n 80'],stdout=out,stderr=subprocess.STDOUT,timeout=15)
        for name in ['build-controller.log','install.log','result.json','packages.tsv','*.deb','*.dsc','*.tar.xz','*.buildinfo','*.changes']:
            subprocess.run(scp+['builder@127.0.0.1:/home/builder/niayan-monitor/'+name,str(work)],check=False,timeout=30)
        subprocess.run(ssh+['sudo poweroff'],capture_output=True,timeout=15)
        vm.wait(timeout=45)
        (work/'exit.json').write_text(json.dumps(dict(guest=result.returncode,qemu=vm.returncode,ram_mib=2048,vcpus=1))+'\n')
        if result.returncode:raise SystemExit(result.returncode)
    finally:
        if vm.poll() is None:
            vm.terminate()
            try:vm.wait(timeout=10)
            except subprocess.TimeoutExpired:vm.kill();vm.wait(timeout=5)
