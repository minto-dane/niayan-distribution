#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Real polkit acceptance, ONLY in an explicitly disposable root test VM.

The local test rule authorizes one fixture user/plan/request. It is not a
production rule, user confirmation UI, or native supply/generation admission.
"""
import argparse
import ctypes as C
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import pwd
import socket
import subprocess
import tempfile
import time

PLAN=b'2'*64;REQUEST=b'1'*32
RULE=Path('/etc/polkit-1/rules.d/00-nia-operator-test.rules')


def run(*args):return subprocess.run(args,check=True,capture_output=True,timeout=20)


class Decision:
    def __init__(self,path):
        self.lib=C.CDLL(str(path));self.handle=C.c_void_p()
        self.lib.nia_operator_open.argtypes=[C.POINTER(C.c_void_p),C.c_int,C.c_char_p,C.c_char_p,C.c_ulonglong,C.c_int]
        self.lib.nia_operator_open.restype=C.c_int
        self.lib.nia_operator_check.argtypes=[C.c_void_p,C.c_char_p,C.c_char_p];self.lib.nia_operator_check.restype=C.c_int
        self.lib.nia_operator_close.argtypes=[C.POINTER(C.c_void_p)];self.lib.nia_operator_close.restype=None
    def open(self,peer,plan=PLAN,request=REQUEST,deadline=None):
        if deadline is None:deadline=int(time.clock_gettime(time.CLOCK_BOOTTIME)*1000)+10000
        return self.lib.nia_operator_open(C.byref(self.handle),peer.fileno(),plan,request,deadline,0)
    def check(self,plan=PLAN,request=REQUEST):return self.lib.nia_operator_check(self.handle,plan,request)
    def close(self):self.lib.nia_operator_close(C.byref(self.handle))


class Peer:
    def __init__(self,directory,uid,gid):
        self.path=directory/'peer.sock'
        listener=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET);listener.bind(str(self.path));self.path.chmod(0o666);listener.listen(1);listener.settimeout(5)
        self.parent,child=multiprocessing.Pipe()
        def client():
            self.parent.close();listener.close();os.setgroups([]);os.setgid(gid);os.setuid(uid)
            peer=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET);peer.connect(str(self.path));peer.sendall(b'fixture-request')
            while True:
                command=child.recv()
                if command=='cancel':peer.sendall(b'cancel');child.send('sent')
                else:break
            peer.close();child.close()
        self.process=multiprocessing.get_context('fork').Process(target=client);self.process.start();child.close()
        self.peer,_=listener.accept();listener.close();assert self.peer.recv(64)==b'fixture-request'
    def cancel(self):self.parent.send('cancel');assert self.parent.recv()=='sent'
    def disconnect(self):
        self.parent.send('close');self.process.join(5);assert self.process.exitcode==0
    def close(self):
        if self.process.is_alive():self.disconnect()
        self.peer.close();self.parent.close();self.process.close();self.path.unlink()


def rule(allow):
    result='YES' if allow else 'NO'
    raw=('polkit.addRule(function(action, subject) {\n'
         '  if (action.id == "org.niaos.package.manage" && subject.user == "builder" &&\n'
         f'      action.lookup("nia.plan") == "{PLAN.decode()}" &&\n'
         f'      action.lookup("nia.request") == "{REQUEST.decode()}") return polkit.Result.{result};\n'
         '});\n')
    temporary=RULE.with_suffix('.temporary');temporary.write_text(raw);temporary.chmod(0o644);temporary.replace(RULE)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True);parser.add_argument('--ada',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True);parser.add_argument('--disposable-vm',action='store_true',required=True)
    args=parser.parse_args();assert os.getuid()==os.geteuid()==0 and not RULE.exists()
    assert Path('/sys/class/dmi/id/product_name').read_text().strip().startswith('Standard PC')
    run('systemctl','start','polkit.service')
    policy=run('pkaction','--action-id','org.niaos.package.manage','--verbose').stdout.decode()
    assert 'auth_admin' in policy and 'auth_admin_keep' not in policy
    args.report.with_suffix('.policy.txt').write_text(policy)
    account=pwd.getpwnam('builder');passed=[];context=Decision(args.library)
    try:
        with tempfile.TemporaryDirectory(prefix='nia-operator-') as temporary:
            directory=Path(temporary);directory.chmod(0o755)
            peer=Peer(directory,account.pw_uid,account.pw_gid)
            try:
                assert context.open(peer.peer)==1 and not context.handle.value;passed.append('default-denies-without-authentication')
                rule(True);run('systemctl','restart','polkit.service')
                assert context.open(peer.peer)==0 and context.check()==0;passed.append('real-pidfd-subject-and-exact-rule')
                assert context.open(peer.peer)==4;passed.append('busy-handle')
                assert context.check(plan=b'3'*64)==1 and context.check()==1;passed.append('context-mismatch-poisons')
                context.close();os.fstat(peer.peer.fileno());passed.append('borrowed-peer-preserved')
                assert context.open(peer.peer,plan=b'3'*64)==1;passed.append('unapproved-plan')
                assert context.open(peer.peer,request=b'3'*32)==1;passed.append('unapproved-request')
                env=dict(os.environ,NIA_TEST_OPERATOR_FD=str(peer.peer.fileno()),DBUS_SYSTEM_BUS_ADDRESS='unix:path=/does-not-exist')
                result=subprocess.run([str(args.ada)],env=env,pass_fds=(peer.peer.fileno(),),check=True,capture_output=True,timeout=15)
                args.report.with_suffix('.ada.log').write_bytes(result.stdout+result.stderr);passed.append('ada-live-ffi-fixed-system-bus')
                assert context.open(peer.peer)==0
                rule(False);until=time.monotonic()+6
                while context.check()==0:
                    if time.monotonic()>=until:raise TimeoutError('polkit Changed invalidation')
                    time.sleep(.05)
                assert context.check()==1;context.close();assert context.open(peer.peer)==1
                passed.append('live-rule-revocation-and-poison')
                rule(True);run('systemctl','restart','polkit.service');assert context.open(peer.peer)==0
                run('systemctl','restart','polkit.service');assert context.check()==1;context.close();passed.append('authority-restart-invalidates')
                assert context.open(peer.peer)==0;peer.cancel();assert context.check()==1;context.close();passed.append('cancel-packet-invalidates')
            finally:context.close();peer.close()
            peer=Peer(directory,account.pw_uid,account.pw_gid)
            try:
                assert context.open(peer.peer)==0;peer.disconnect();assert context.check()==1;context.close();passed.append('peer-exit-invalidates')
            finally:context.close();peer.close()
            peer=Peer(directory,account.pw_uid,account.pw_gid)
            try:
                deadline=int(time.clock_gettime(time.CLOCK_BOOTTIME)*1000)+2000
                assert context.open(peer.peer,deadline=deadline)==0
                time.sleep(2.1);assert context.check()==3 and context.handle.value
                context.close();passed.append('finite-deadline-no-renewal')
            finally:context.close();peer.close()
            nobody=pwd.getpwnam('nobody');peer=Peer(directory,nobody.pw_uid,nobody.pw_gid)
            try:assert context.open(peer.peer)==1;passed.append('wrong-actor-denied')
            finally:context.close();peer.close()
    finally:
        context.close()
        if RULE.exists():RULE.unlink();run('systemctl','restart','polkit.service')
    result=dict(result='pass',checks=passed,library_sha256=hashlib.sha256(args.library.read_bytes()).hexdigest(),
                test_rule_removed=not RULE.exists(),polkit_version=run('dpkg-query','-W','-f=${Version}','polkitd').stdout.decode(),
                authentication_dialog_exercised=False,native_admission=False,exact_plan_consent=False,boot_switched=False)
    args.report.write_text(json.dumps(result,indent=2)+'\n');print('PASS real polkit operator authorization',len(passed))


if __name__=='__main__':main()
