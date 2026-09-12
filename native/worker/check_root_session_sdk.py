#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Real controller and native supervisor transport on a disposable GPT/ext4 VM.

Requires explicit storage bootstrap. The request/archive and admission are test
fixtures. The shared library is compiled from the private native C adapter.
"""
import argparse
import ctypes as C
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import sys
import time

from check_root_session_transport import Client
from check_root_session import BASE, BANK, WORKER, SOCKET, UNIT, run
from check_root_extract import archive
from check_root_reinspection import snapshot
sys.path.insert(0,'/usr/libexec/niaos')
from root_bank import Bank, mount_identity
from storage_bootstrap import check_bank


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();assert os.getuid()==os.geteuid()==0
    assert not (BASE/'root-session.json').exists()
    account=pwd.getpwnam('nia-pkg');bank=check_bank();assert bank['readonly']
    raw,count=archive();path=args.report.parent/'native-session.tar';path.write_bytes(raw);path.chmod(0o444)
    source=os.open(path,os.O_RDONLY|os.O_CLOEXEC)
    def lease():
        fd=os.open(BASE/'core/store/store.lock',os.O_RDWR|os.O_CLOEXEC)
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);return fd
    original=lease();client=Client(args.library)
    run('systemctl','start','niaos-root-session.socket',UNIT)
    deadline=int(time.clock_gettime(time.CLOCK_BOOTTIME)*1000)+60000
    worker=hashlib.sha256(WORKER.read_bytes()).hexdigest()
    plan=hashlib.sha256(Path('/etc/niaos/root-bank-device.json').read_bytes()).hexdigest()
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    identity=bank['identity'];stage='1'*32
    try:
        result=client.lib.nia_root_session_open(C.byref(client.handle),SOCKET.encode(),b'2'*64,b'3'*64,
            hashlib.sha256(raw).hexdigest().encode(),worker.encode(),stage.encode(),plan.encode(),boot.encode(),
            len(raw),count,deadline,identity['mount_id'],identity['inode'],identity['device_major'],identity['device_minor'],
            source,original,C.byref(client.inode))
        assert result==0 and client.held(),result
        os.close(original);original=-1
        fresh=lease()
        try:
            try:other=Bank(BANK,BASE/'core/store/store.lock',WORKER,account.pw_uid)
            except BlockingIOError:pass
            else:other.close();raise AssertionError('bank released before Close')
            # Independent held FD, not the socket response, confirms the actual
            # root mount/device/inode and RO state before using its observation.
            physical=os.open(BANK/stage/'root',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            try:
                info=os.fstat(physical)
                observed=dict(mount_id=mount_identity(physical),inode=info.st_ino,
                    device_major=os.major(info.st_dev),device_minor=os.minor(info.st_dev))
                assert observed==dict(identity,inode=client.inode.value)
                assert os.fstatvfs(physical).f_flag & os.ST_RDONLY
                before=snapshot(BANK/stage/'root')
                records=[(BANK/stage/n).read_bytes() for n in ('intent.json','result.json')]
                assert client.lib.nia_root_session_observe(client.handle,source,fresh)==0 and client.held()
                close_result=client.close();assert close_result==0,close_result
                assert not client.held() and not client.handle.value
                assert client.lib.nia_root_session_observe(client.handle,source,fresh)==1
            finally:os.close(physical)
        finally:os.close(fresh)
        until=time.monotonic()+8
        while True:
            try:other=Bank(BANK,BASE/'core/store/store.lock',WORKER,account.pw_uid);other.close();break
            except BlockingIOError:
                if time.monotonic()>=until:raise
                time.sleep(.05)
        assert check_bank()['readonly'] and snapshot(BANK/stage/'root')==before
        assert [(BANK/stage/n).read_bytes() for n in ('intent.json','result.json')]==records
        os.fstat(source)
        assert json.loads((BASE/'root-session-complete.json').read_text())['bank_readonly']
        args.report.write_text(json.dumps(dict(result='pass',native_prepare=True,independent_root=observed,
            cas_reacquired=True,bank_retained=True,native_observe=True,close_eof_acknowledged=close_result==0,closed_observe_refused=True,
            tree_and_records_unchanged=True,bank_readonly_after_close=True,worker_sha256=worker,
            native_library_sha256=hashlib.sha256(args.library.read_bytes()).hexdigest(),
            site_admission_fixture=True,generation_sdk_connected=False,boot_switched=False),indent=2)+'\n')
        print('PASS real controller through native supervisor transport')
    finally:
        client.discard()
        if original>=0:os.close(original)
        os.close(source)
        run('systemctl','stop','niaos-root-session.socket',UNIT)


if __name__=='__main__':main()
