# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import json, subprocess, tempfile, time
from vm_console import retire_install_disks
with tempfile.TemporaryDirectory(dir='/evidence',prefix='owned-qemu-lock-') as temporary:
    root=Path(temporary)
    disks=[]
    for name in ('install-uefi-offline','install-bios-network'):
        directory=root/name;directory.mkdir()
        disk=directory/'installed.qcow2';disks.append(disk)
        subprocess.run(['qemu-img','create','-f','qcow2',str(disk),'8M'],check=True,stdout=subprocess.DEVNULL)
    with (root/'qemu.log').open('wb') as log:
        child=subprocess.Popen(['qemu-system-x86_64','-machine','q35','-accel','tcg','-m','32','-S','-nodefaults','-display','none','-monitor','none','-serial','none','-drive','file='+str(disks[1])+',format=qcow2,if=virtio'],stdout=log,stderr=subprocess.STDOUT)
        try:
            # The readiness probe requests the same image access and must
            # report its write lock conflict, not merely a running PID.
            for _ in range(100):
                if child.poll() is not None:raise RuntimeError((root/'qemu.log').read_text())
                probe=subprocess.run(['qemu-img','info',str(disks[1])],capture_output=True)
                if probe.returncode and b'lock' in probe.stderr:break
                time.sleep(.02)
            else:raise RuntimeError('QEMU image lock was not observed')
            try:retire_install_disks(root,[])
            except BlockingIOError:pass
            else:raise AssertionError('active QEMU disk was retired')
            assert all(disk.exists() for disk in disks)
        finally:
            child.terminate();child.wait(timeout=5)
    records=[];retire_install_disks(root,records)
    assert all(not disk.exists() for disk in disks)
    Path('/evidence/qemu-disk-retirement.json').write_text(json.dumps(dict(result='pass',real_qemu_lock_refused=True,no_disk_removed_while_busy=True,closed_disks_retired=True,records=records),indent=2)+'\n')
