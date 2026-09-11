#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Root-supervisor session acceptance on an explicitly bootstrapped disposable VM."""
import argparse
import array
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import subprocess
import sys
import time

sys.path.insert(0,'/usr/libexec/niaos')
from root_bank import Bank, canonical
from storage_bootstrap import check_bank
from check_root_extract import archive
from check_root_reinspection import snapshot

BASE=Path('/var/lib/niaos');BANK=BASE/'roots';WORKER=Path('/usr/libexec/niaos/root-extract')
SOCKET='/run/niaos/root-session.sock';UNIT='niaos-root-session.service'


def run(*args):return subprocess.run(args,check=True,capture_output=True,timeout=45)


def connect():
    peer=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET);peer.settimeout(8);peer.connect(SOCKET);return peer


def send(peer,value,descriptors=()):
    controls=[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',descriptors))] if descriptors else []
    peer.sendmsg([canonical(value)],controls)


def terminal(peer):
    frames=[]
    while True:
        raw=peer.recv(4096)
        if not raw:break
        frames.append(json.loads(raw))
    peer.close();return frames


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--ending',choices=('close','disconnect','expire','kill'),default='close')
    parser.add_argument('--after-reboot',action='store_true')
    args=parser.parse_args();assert os.getuid()==os.geteuid()==0
    if args.after_reboot:
        result=json.loads(args.report.read_text());assert result['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        run('systemctl','start','var-lib-niaos-roots.mount');assert check_bank()['readonly']
        assert hashlib.sha256((BASE/'root-session.json').read_bytes()).hexdigest()==result['attempt_sha256']
        denied=subprocess.run(['systemctl','start','niaos-root-preparation.socket','niaos-root-preparation.service'],capture_output=True,timeout=45)
        assert denied.returncode!=0
        result['reboot_readonly_and_old_writer_refused']=True;args.report.write_text(json.dumps(result,indent=2)+'\n');return
    assert not (BASE/'root-session.json').exists()
    account=pwd.getpwnam('nia-pkg');policy=Path('/etc/niaos/root-bank-device.json').read_bytes()
    run('systemctl','start','niaos-root-session.socket',UNIT)
    denial=subprocess.run(['/usr/bin/python3','-I','-c',"import socket;s=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET);s.connect('/run/niaos/root-session.sock')"],user=account.pw_uid,group=account.pw_gid,extra_groups=[],capture_output=True,timeout=5)
    assert denial.returncode!=0
    raw,count=archive();path=args.report.parent/'session.tar';path.write_bytes(raw);path.chmod(0o444)
    source=os.open(path,os.O_RDONLY)
    def lease():
        fd=os.open(BASE/'core/store/store.lock',os.O_RDWR);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);return fd
    original=lease()
    deadline=int(time.clock_gettime(time.CLOCK_BOOTTIME)*1000)+(7000 if args.ending=='expire' else 60000)
    request=dict(version=1,stage='1'*32,generation='2'*64,root_manifest='3'*64,archive=hashlib.sha256(raw).hexdigest(),size=len(raw),entries=count,deadline_ms=deadline)
    message=dict(version=1,operation='prepare-freeze',request=request,worker_sha256=hashlib.sha256(WORKER.read_bytes()).hexdigest(),
                 device_plan_sha256=hashlib.sha256(policy).hexdigest(),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),bank=check_bank()['identity'])
    refusals=[]
    for name,changed,fds in (
        ('wrong-worker',dict(message,worker_sha256='0'*64),(source,original)),
        ('wrong-mount',dict(message,bank=dict(message['bank'],mount_id=message['bank']['mount_id']+1)),(source,original)),
        ('wrong-device-plan',dict(message,device_plan_sha256='0'*64),(source,original)),
        ('missing-descriptors',message,())):
        peer=connect();send(peer,changed,fds);frames=terminal(peer)
        assert frames==[dict(version=1,state='refused-or-indeterminate',published=False)],frames
        assert not (BASE/'root-session.json').exists() and check_bank()['readonly'];refusals.append(name)
    peer=connect();send(peer,message,(source,original));ready=json.loads(peer.recv(4096))
    assert ready['state']=='frozen' and not ready['published'],ready
    os.close(original);original=-1
    # Readiness is sent after the server closes received CAS copies. A fresh
    # independent OFD must now succeed while the bank remains reserved.
    fresh=lease()
    try:
        try:other=Bank(BANK,BASE/'core/store/store.lock',WORKER,account.pw_uid)
        except BlockingIOError:pass
        else:other.close();raise AssertionError('controller released bank early')
        send(peer,dict(version=1,operation='observe',stage=request['stage']),(source,fresh))
        observed=json.loads(peer.recv(4096));assert observed==ready
    finally:os.close(fresh)
    before=snapshot(BANK/request['stage']/'root')
    records=[(BANK/request['stage']/n).read_bytes() for n in ('intent.json','result.json')]
    if args.ending=='close':
        send(peer,dict(version=1,operation='close',stage=request['stage']));assert terminal(peer)==[]
    elif args.ending=='disconnect':peer.close()
    elif args.ending=='expire':
        peer.settimeout(10);frames=terminal(peer);assert frames==[dict(version=1,state='refused-or-indeterminate',published=False)]
    else:
        # Explicit privileged drift of this test partition, followed by killing
        # the controller. The independent systemd stop hook must restore RO.
        run('mount','-o','remount,rw,nodev,nosuid,noexec',str(BANK));assert not check_bank()['readonly']
        run('systemctl','kill','--signal=SIGKILL','--kill-whom=all',UNIT);terminal(peer)
    until=time.monotonic()+12
    while True:
        try:
            other=Bank(BANK,BASE/'core/store/store.lock',WORKER,account.pw_uid);other.close()
            if check_bank()['readonly']:break
        except BlockingIOError:pass
        if time.monotonic()>=until:raise TimeoutError('controller cleanup')
        time.sleep(0.05)
    assert snapshot(BANK/request['stage']/'root')==before
    assert [(BANK/request['stage']/n).read_bytes() for n in ('intent.json','result.json')]==records
    if args.ending=='kill':assert not (BASE/'root-session-complete.json').exists()
    else:assert json.loads((BASE/'root-session-complete.json').read_text())['bank_readonly'] is True
    os.close(source)
    attempt_hash=hashlib.sha256((BASE/'root-session.json').read_bytes()).hexdigest()
    if args.ending!='kill':
        retry=dict(message,request=dict(request,deadline_ms=int(time.clock_gettime(time.CLOCK_BOOTTIME)*1000)+60000))
        source=os.open(path,os.O_RDONLY);fresh=lease()
        try:
            peer=connect();send(peer,retry,(source,fresh));frames=terminal(peer)
            assert frames==[dict(version=1,state='refused-or-indeterminate',published=False)]
        finally:os.close(source);os.close(fresh)
        assert hashlib.sha256((BASE/'root-session.json').read_bytes()).hexdigest()==attempt_hash
    run('systemctl','stop','niaos-root-session.socket',UNIT)
    result=dict(result='pass',ending=args.ending,unauthorized_user_refused=True,refusals=refusals,
                ready=ready,cas_reacquired_before_observe=True,bank_retained_until_end=True,original_tree_and_records_unchanged=True,
                bank_readonly_after_end=True,attempt_sha256=attempt_hash,reused_bank_refused=args.ending!='kill',
                stop_hook_after_privileged_drift=args.ending=='kill',boot_id=message['boot_id'],site_admission_fixture=True,
                native_sdk_connected=False,boot_switched=False)
    args.report.write_text(json.dumps(result,indent=2)+'\n');print('PASS privileged root session:',args.ending)


if __name__=='__main__':main()
