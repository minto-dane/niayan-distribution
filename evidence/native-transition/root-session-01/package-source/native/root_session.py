#!/usr/bin/python3 -I
# SPDX-License-Identifier: BSD-3-Clause
"""Root-supervisor RPC for one fresh dedicated bank, with retained physical exclusion.

Root credentials are control-plane authority, not user consent or supply proof.
A trusted supervisor must first run native admission and retain its own scope.
"""
import array
import contextlib
import ctypes
import hashlib
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bank_device
from root_bank import Bank, Rejected, canonical, decode, read_policy, validate_request
from root_freeze import FrozenRoot, clock_check, filesystem, readonly_filesystem
from storage_bootstrap import BASE, POLICY, check_bank, record, root_directory, protected_file

CHILD = '/usr/libexec/niaos/root_session_worker.py'
ATTEMPT = 'root-session.json'
COMPLETE = 'root-session-complete.json'
CAPS = '-all,+chown,+dac_override,+fowner,+fsetid,+sys_chroot,+mknod,+setfcap'
MASK = sum(1 << n for n in (0,1,3,4,18,27,31))


def receive(peer, expected_pid, timeout):
    descriptors=[]
    try:
        peer.settimeout(timeout)
        raw,controls,flags,_=peer.recvmsg(4096,socket.CMSG_SPACE(12)+socket.CMSG_SPACE(8),socket.MSG_CMSG_CLOEXEC)
        credentials=[];invalid=False
        for level,kind,data in controls:
            if level==socket.SOL_SOCKET and kind==socket.SCM_RIGHTS:
                values=array.array('i');invalid |= bool(len(data)%values.itemsize)
                values.frombytes(data[:len(data)-len(data)%values.itemsize]);descriptors.extend(values)
            elif level==socket.SOL_SOCKET and kind==socket.SCM_CREDENTIALS and len(data)==12:
                credentials.append(struct.unpack('3i',data))
            else:invalid=True
        if not raw and not descriptors and not controls:return None,[]
        if (invalid or flags & (socket.MSG_TRUNC|socket.MSG_CTRUNC) or len(credentials)!=1
                or credentials[0][0]!=expected_pid or credentials[0][1]!=0 or len(descriptors)>2):
            raise Rejected('controller-sender-or-controls')
        return decode(raw),descriptors
    except BaseException:
        for fd in descriptors:os.close(fd)
        raise


def remaining(deadline):
    clock_check(deadline)
    return (deadline-time.clock_gettime(time.CLOCK_BOOTTIME)*1000)/1000


def writable(fd):
    libc=ctypes.CDLL(None,use_errno=True);mount=libc.mount
    mount.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_ulong,ctypes.c_void_p];mount.restype=ctypes.c_int
    if mount(None,f'/proc/self/fd/{fd}'.encode(),None,32|2|4|8,None):
        number=ctypes.get_errno();raise OSError(number,os.strerror(number))


def child_operation(bank, operation, request, archive, lease):
    args=['/usr/bin/setpriv','--bounding-set='+CAPS,'--inh-caps=-all','--ambient-caps=-all',
          '--no-new-privs','--pdeathsig','KILL','/usr/bin/python3','-I',CHILD,'--operation',operation,
          '--archive-fd',str(archive),'--lease-fd',str(lease),'--bank-lock-fd',str(bank.lock),'--parent',str(os.getpid()),'--worker-sha256',bank.worker_hash]
    child=subprocess.Popen(args,pass_fds=(archive,lease,bank.lock),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                           env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C.UTF-8'})
    try:
        stdout,stderr=child.communicate(canonical(request),timeout=remaining(request['deadline_ms']))
    except BaseException:
        child.kill();child.communicate();raise
    if child.returncode or stderr or len(stdout)>4096:raise Rejected('controller-worker')
    result=decode(stdout)
    if result.pop('child_capability_mask',None)!=MASK:raise Rejected('controller-worker-capabilities')
    return result


def serve_session(peer):
    descriptors=[];bank=None;frozen=None;device=base=-1;attempt=False;readonly=False
    deadline=None;request=None;plan_raw=None;expected=None
    try:
        pid,uid,_=struct.unpack('3i',peer.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        if uid!=0 or pid<=0:raise Rejected('root-supervisor-required')
        peer.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,1)
        message,descriptors=receive(peer,pid,2)
        fields={'version','operation','request','worker_sha256','device_plan_sha256','boot_id','bank'}
        if (type(message) is not dict or set(message)!=fields or type(message['version']) is not int
                or message['version']!=1 or message['operation']!='prepare-freeze' or len(descriptors)!=2):
            raise Rejected('controller-request')
        request=message['request'];validate_request(request);deadline=request['deadline_ms'];remaining(deadline)
        if message['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():raise Rejected('controller-boot')
        plan,plan_raw=bank_device.selection()
        if message['device_plan_sha256']!=hashlib.sha256(plan_raw).hexdigest():raise Rejected('controller-device-plan')
        observed=check_bank()
        if not observed['readonly'] or canonical(message['bank'])!=canonical(observed['identity']):raise Rejected('controller-bank-selection')
        expected=observed['identity'];device=bank_device.open_device(plan)
        policy=read_policy(Path(POLICY))
        if policy['bank']!=bank_device.BANK or policy['reservation']!=BASE+'/core/store/store.lock':raise Rejected('controller-fixed-storage')
        bank=Bank(policy['bank'],policy['reservation'],policy['worker'],policy['client_uid'])
        if message['worker_sha256']!=bank.worker_hash:raise Rejected('controller-worker-pin')
        bank.check_inputs(request,*descriptors)
        if set(os.listdir(bank.directory))!={'bank.json','bank.lock'}:raise Rejected('controller-bank-not-fresh')
        if filesystem(bank.directory,expected)!=(expected,True):raise Rejected('controller-bank-not-readonly')
        base=root_directory(BASE)
        try:os.stat(COMPLETE,dir_fd=base,follow_symlinks=False)
        except FileNotFoundError:pass
        else:raise Rejected('controller-existing-completion')
        # O_EXCL is the durable first-use barrier. It is never removed on retry,
        # failure, disconnect, normal Close, or restart. This bank is not recycled.
        record(base,ATTEMPT,{'version':1,'request':request,'worker_sha256':bank.worker_hash,
            'device_plan_sha256':hashlib.sha256(plan_raw).hexdigest(),'boot_id':message['boot_id'],'published':False})
        attempt=True
        try:
            remaining(deadline);writable(bank.directory)
            prepared=child_operation(bank,'prepare',request,*descriptors)
            if prepared!=bank.inspect(request['stage']) or prepared['state']!='extracted':raise Rejected('controller-extraction')
        finally:
            readonly_filesystem(bank.directory)
        frozen=FrozenRoot();frozen.acquire(bank,request,*descriptors,expected)
        verified=child_operation(bank,'verify',request,*descriptors)
        if not verified.get('physical_revalidation'):raise Rejected('controller-reinspection')
        observation=frozen.observe(*descriptors)
        current_plan,current_raw=bank_device.selection()
        if current_raw!=plan_raw or bank_device.mounted(device)!=(expected,True):raise Rejected('controller-device-changed')
        bank_device.verify_mount_configuration(current_plan)
        # Release received CAS/archive copies BEFORE readiness. The caller may
        # now acquire a new native CAS OFD while the controller keeps bank/device.
        for fd in descriptors:os.close(fd)
        descriptors=[]
        peer.settimeout(remaining(deadline))
        peer.sendall(canonical({'version':1,'state':'frozen','stage':request['stage'],
                                'observation':observation,'deadline_ms':deadline,'published':False}))
        while True:
            message,descriptors=receive(peer,pid,remaining(deadline))
            if message is None:break
            if type(message) is not dict or set(message)!={'version','operation','stage'} or type(message['version']) is not int or message['version']!=1 or message['stage']!=request['stage']:
                raise Rejected('controller-session-request')
            if message['operation']=='close' and not descriptors:break
            if message['operation']!='observe' or len(descriptors)!=2:raise Rejected('controller-session-operation')
            current_plan,current_raw=bank_device.selection()
            if current_raw!=plan_raw or bank_device.mounted(device)!=(expected,True):raise Rejected('controller-device-changed')
            bank_device.verify_mount_configuration(current_plan)
            observation=frozen.observe(*descriptors)
            for fd in descriptors:os.close(fd)
            descriptors=[]
            peer.settimeout(remaining(deadline))
            peer.sendall(canonical({'version':1,'state':'frozen','stage':request['stage'],'observation':observation,
                                    'deadline_ms':deadline,'published':False}))
    except (OSError,ValueError,subprocess.SubprocessError):
        # A refusal after RW was attempted is indeterminate, never a rollback.
        with contextlib.suppress(OSError):
            peer.settimeout(1);peer.sendall(canonical({'version':1,'state':'refused-or-indeterminate','published':False}))
    finally:
        if bank is not None and attempt:
            try:
                readonly_filesystem(bank.directory)
                _,readonly=filesystem(bank.directory,expected)
                record(base,COMPLETE,{'version':1,'state':'session-ended','bank_readonly':readonly,
                                      'stage':request['stage'],'published':False,'boot_authorized':False})
            except (OSError,ValueError):
                # Preserve the attempt without inventing a completed cleanup.
                pass
        if frozen is not None:frozen.close()
        if bank is not None:bank.close()
        for fd in descriptors:os.close(fd)
        if device>=0:os.close(device)
        if base>=0:os.close(base)
        # EOF acknowledges that this controller has released its own FDs. It
        # makes no assertion about supervisor-held or unrelated privileged FDs.
        peer.close()


def seal_after_stop():
    # systemd runs this after terminating the complete controller cgroup. It
    # never opens storage RW and never converts an interrupted attempt to success.
    if not Path(BASE,ATTEMPT).exists():return
    saved=decode(protected_file(BASE+'/'+ATTEMPT,mode=0o600,limit=4096))
    plan,raw=bank_device.selection()
    if saved.get('device_plan_sha256')!=hashlib.sha256(raw).hexdigest():raise Rejected('stop-seal-device-plan')
    check_bank();device=bank_device.open_device(plan)
    try:
        bank_device.mounted(device)
        directory=root_directory(bank_device.BANK)
        try:readonly_filesystem(directory)
        finally:os.close(directory)
        if not bank_device.mounted(device)[1]:raise Rejected('stop-seal-not-readonly')
    finally:os.close(device)
    print(canonical({'version':1,'state':'bank-sealed-after-stop','published':False}).decode(),end='')


def main():
    if os.getuid() or os.geteuid():raise Rejected('controller-privilege')
    if sys.argv[1:]==['--seal-bank']:
        seal_after_stop();return
    if len(sys.argv)!=1:raise Rejected('controller-arguments')
    if os.environ.get('LISTEN_PID')!=str(os.getpid()) or os.environ.get('LISTEN_FDS')!='1':raise Rejected('controller-activation')
    listener=socket.socket(fileno=3)
    if listener.family!=socket.AF_UNIX or listener.type!=socket.SOCK_SEQPACKET:raise Rejected('controller-listener')
    # Enable before accept so queued first messages carry kernel credentials.
    listener.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,1)
    while True:
        peer,_=listener.accept();serve_session(peer)


if __name__=='__main__':main()
