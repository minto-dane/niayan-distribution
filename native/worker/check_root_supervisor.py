#!/usr/bin/python3
# SPDX-License-Identifier: BSD-3-Clause
"""Integrated native handoff/polkit/root effects in an explicitly disposable VM.

Scope/CAS/admission are fixtures, never a production provider. Cancellation uses
real polkit revocation while the real native extraction worker is stopped.
"""
import argparse
import ctypes as C
import dataclasses
import fcntl
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import pwd
import select
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time

from check_operator_authorization import PLAN, REQUEST, RULE, Peer, rule, run

sys.path.insert(0, '/usr/libexec/niaos')
from operator_guard import OperatorGuard
from root_handoff import Channel, Scope, ReinspectionScope, now_ms
from root_session_client import RootSession
from root_supervisor import Supervisor
from plan_consent import Offer, PlanConsent
from storage_bootstrap import check_bank


def inject(controller, report):
    pinned = os.pidfd_open(controller)
    target = -1
    try:
        until = time.monotonic() + 15
        while time.monotonic() < until:
            assert not select.select([pinned], [], [], 0)[0]
            children = Path(f'/proc/{controller}/task/{controller}/children').read_text().split()
            for child in children:
                try:
                    descendants = Path(f'/proc/{child}/task/{child}/children').read_text().split()
                    for descendant in descendants:
                        if os.readlink(f'/proc/{descendant}/exe') == '/usr/libexec/niaos/root-extract':
                            target = os.pidfd_open(int(descendant))
                            signal.pidfd_send_signal(target, signal.SIGSTOP)
                            break
                except FileNotFoundError:
                    continue
                if target >= 0:
                    break
            if target >= 0:
                break
            time.sleep(.001)
        assert target >= 0, 'real extraction worker was not observed'
        bank = Path('/var/lib/niaos/roots')
        assert not os.statvfs(bank).f_flag & os.ST_RDONLY
        attempt = Path('/var/lib/niaos/root-session.json').read_bytes()
        started = time.monotonic()
        rule(False)  # Actual Changed signal, no fake observer result.
        assert select.select([target], [], [], 5)[0], 'revoked native worker still running'
        completed = Path('/var/lib/niaos/root-session-complete.json')
        for _ in range(500):
            if completed.exists():
                break
            time.sleep(.01)
        result = json.loads(completed.read_bytes())
        assert result['bank_readonly'] and not result['published'] and not result['boot_authorized']
        assert check_bank()['readonly'] and Path('/var/lib/niaos/root-session.json').read_bytes() == attempt
        report.write_text(json.dumps(dict(worker_stopped=True, revocation_seconds=time.monotonic()-started,
            bank_readonly=True, original_attempt_preserved=True, completion=result), indent=2)+'\n')
    finally:
        if target >= 0:
            try:
                signal.pidfd_send_signal(target, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.close(target)
        os.close(pinned)


class FixtureAdmission:
    def __init__(self, scope):
        self.scope = scope
        self.boundaries = set()

    def check(self, scope, plan, request, boundary):
        assert scope == self.scope and plan.hex() == PLAN.decode() and request.hex() == REQUEST.decode()
        self.boundaries.add(boundary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable-vm', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--library', type=Path)
    parser.add_argument('--cancel', action='store_true')
    parser.add_argument('--inject', type=int)
    args = parser.parse_args()
    assert __debug__ and os.getuid() == os.geteuid() == 0
    assert run('systemd-detect-virt', '--vm').stdout.strip() in (b'kvm', b'qemu')
    if args.inject is not None:
        inject(args.inject, args.report)
        return
    assert not RULE.exists() and not Path('/var/lib/niaos/root-session.json').exists()
    assert check_bank()['readonly']
    source = args.report.parent / 'supervisor.tar'
    with tarfile.open(source, 'w', format=tarfile.USTAR_FORMAT) as archive:
        directory = tarfile.TarInfo('.')
        directory.type, directory.mode = tarfile.DIRTYPE, 0o755
        archive.addfile(directory)
        item = tarfile.TarInfo('payload')
        item.size = 32 * 1024 * 1024 if args.cancel else 4096
        archive.addfile(item, io.BytesIO(bytes(item.size)))
    source.chmod(0o444)
    worker = Path('/usr/libexec/niaos/root-extract')
    scope = Scope(bytes.fromhex('22'*32), bytes.fromhex('33'*32), hashlib.sha256(source.read_bytes()).digest(),
        hashlib.sha256(worker.read_bytes()).digest(), bytes.fromhex('11'*16), source.stat().st_size, 2, now_ms()+60_000)
    archive_fd = os.open(source, os.O_RDONLY | os.O_CLOEXEC)
    lease = os.open('/var/lib/niaos/core/store/store.lock', os.O_RDWR | os.O_CLOEXEC)
    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    pairs = [socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET) for _ in range(2)]
    for pair in pairs:
        for peer in pair:
            peer.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    native = C.CDLL(str(args.library))
    native.nia_root_handoff_open.argtypes = [C.POINTER(C.c_void_p), C.c_int, C.c_ulonglong]
    for name in ('nia_root_handoff_prepare', 'nia_root_handoff_reinspect'):
        getattr(native, name).argtypes = [C.c_void_p, C.c_void_p, C.c_int, C.c_int]
    native.nia_root_handoff_close.argtypes = [C.POINTER(C.c_void_p)]
    native.nia_root_handoff_close.restype = None
    parent, child = multiprocessing.Pipe()
    account = pwd.getpwnam('nia-pkg')
    pid = os.fork()
    if not pid:
        try:
            parent.close()
            for root, _ in pairs:
                root.close()
            os.setgroups([])
            os.setgid(account.pw_gid)
            os.setuid(account.pw_uid)
            assert child.recv() == 'begin'
            for index, name in enumerate(('nia_root_handoff_prepare', 'nia_root_handoff_reinspect')):
                wire = scope.wire() if index == 0 else child.recv_bytes()
                context = C.c_void_p()
                assert native.nia_root_handoff_open(C.byref(context), pairs[index][1].fileno(), scope.deadline) == 0
                outcome = getattr(native, name)(context, wire, archive_fd, lease)
                native.nia_root_handoff_close(C.byref(context))
                child.send(outcome)
                assert outcome == (2 if args.cancel else 0), outcome
                if args.cancel:
                    break
            assert child.recv() == 'end'
            os._exit(0)
        except BaseException:
            import traceback
            traceback.print_exc()
            os._exit(1)
    child.close()
    for _, nonroot in pairs:
        nonroot.close()
    supervisor = peer = injector = None
    channel = second = None
    bank = -1
    try:
        run('systemctl', 'start', 'niaos-root-session.socket', 'niaos-root-session.service')
        rule(True)
        run('systemctl', 'restart', 'polkit.service')
        if args.cancel:
            controller = int(run('systemctl', 'show', 'niaos-root-session.service', '--property=MainPID', '--value').stdout)
            injector = subprocess.Popen([sys.executable, __file__, '--disposable-vm', '--inject', str(controller),
                '--report', str(args.report.with_suffix('.injection.json'))])
        with tempfile.TemporaryDirectory(prefix='niayan-supervisor-') as temporary:
            directory = Path(temporary)
            directory.chmod(0o755)
            builder = pwd.getpwnam('builder')
            # The unrelated fixture actor must not retain the launcher's root
            # handoff endpoints through fork and hide their cancellation EOF.
            peer = Peer(directory, builder.pw_uid, builder.pw_gid,
                        close_fds=tuple(root.fileno() for root, _ in pairs))
            bank = os.open('/var/lib/niaos/roots', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            session = RootSession(scope, bank, hashlib.sha256(Path('/etc/niaos/root-bank-device.json').read_bytes()).digest(),
                Path('/proc/sys/kernel/random/boot_id').read_text().strip())
            text = b'Fixture: prepare an inactive root. No catalog or boot activation.\n'
            offer = Offer(bytes.fromhex(REQUEST.decode()), bytes.fromhex(PLAN.decode()), scope.generation,
                hashlib.sha256(text).digest(), scope.deadline, len(text),
                bytes.fromhex(Path('/proc/sys/kernel/random/boot_id').read_text().strip().replace('-', '')))
            consent = PlanConsent(peer.peer, offer)
            consent.send_offer(text)
            peer.confirm_plan()
            assert consent.receive_confirmation()
            guard = OperatorGuard(peer.peer, bytes.fromhex(PLAN.decode()), bytes.fromhex(REQUEST.decode()),
                                  scope.deadline, interactive=False)
            admission = FixtureAdmission(scope)
            supervisor = Supervisor(session, guard, admission, consent=consent)
            channel = Channel(pairs[0][0], pid, account.pw_uid, scope)
            pairs[0][0].close()
            parent.send('begin')
            if args.cancel:
                try:
                    supervisor.prepare(channel)
                except ValueError:
                    pass
                else:
                    raise AssertionError('revoked preparation succeeded')
                assert injector.wait(timeout=8) == 0
                assert parent.poll(5) and parent.recv() == 2
                result = dict(result='pass', real_polkit_revocation_stopped_native_worker=True)
            else:
                observed = supervisor.prepare(channel)
                assert parent.poll(5) and parent.recv() == 0
                second_scope = ReinspectionScope(**dataclasses.asdict(scope), original_deadline=scope.deadline,
                                                 **observed.fields())
                second = Channel(pairs[1][0], pid, account.pw_uid, second_scope)
                pairs[1][0].close()
                parent.send_bytes(second_scope.wire())
                assert supervisor.reinspect(second) == observed
                assert parent.poll(5) and parent.recv() == 0
                supervisor.finish()
                result = dict(result='pass', native_prepare=True, native_reinspect=True,
                    independent_root=observed.fields(), controller_cleanup_eof=True,
                    boundaries=sorted(admission.boundaries))
            parent.send('end')
            assert os.waitpid(pid, 0)[1] == 0
            pid = -1
            os.fstat(archive_fd)
            os.fstat(lease)
            assert check_bank()['readonly']
            result.update(native_supply_and_consent_fixture=True, generation_sdk_connected=False,
                          boot_switched=False, whole_runtime_proof=False)
            args.report.write_text(json.dumps(result, indent=2)+'\n')
            peer.close()
            peer = None
    finally:
        if supervisor is not None:
            supervisor.close()
        if channel is not None:
            channel.close()
        if second is not None:
            second.close()
        if peer is not None:
            peer.close()
        if injector is not None and injector.poll() is None:
            injector.kill()
            injector.wait(timeout=5)
        if pid > 0:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        for root, _ in pairs:
            root.close()
        parent.close()
        for fd in (bank, archive_fd, lease):
            if fd >= 0:
                os.close(fd)
        if RULE.exists():
            RULE.unlink()
            run('systemctl', 'restart', 'polkit.service')


if __name__ == '__main__':
    main()
