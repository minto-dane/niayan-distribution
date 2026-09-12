#!/usr/bin/python3
# SPDX-License-Identifier: BSD-3-Clause
"""Accept the installed asynchronous guard only in an owned disposable VM."""
import argparse
import json
import os
from pathlib import Path
import pwd
import select
import signal
import struct
import subprocess
import sys
import tempfile
import time

from check_operator_authorization import PLAN, REQUEST, RULE, Peer, rule


def run(*args):
    result = subprocess.run(args, capture_output=True, timeout=20)
    if result.returncode:
        raise RuntimeError(str(args) + ": " + result.stderr.decode(errors="replace"))
    return result


def wait_pending(guard):
    while True:
        observation = guard.receive()
        if observation is not None:
            return observation
        pending = select.poll()
        for fd in guard.descriptors():
            pending.register(fd, select.POLLIN)
        pending.poll(min(50, max(1, guard.next_deadline - module.now_ms())))


def observe(guard):
    guard.request_check()
    return wait_pending(guard)


def refusal(operation):
    try:
        operation()
    except (module.Rejected, OSError):
        return
    raise AssertionError('expected rejection')


def main():
    global module
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--disposable-vm', action='store_true', required=True)
    args = parser.parse_args()
    assert os.getuid() == os.geteuid() == 0 and not RULE.exists()
    assert run('systemd-detect-virt','--vm').stdout.strip() in (b'kvm', b'qemu')
    sys.path.insert(0, '/usr/libexec/niaos')
    import operator_guard as module
    account = pwd.getpwnam('builder')
    run('systemctl', 'start', 'polkit.service')
    passed = []
    try:
        for case in ('default-deny', 'valid', 'stale-first-reply', 'wrong-plan', 'rule-change', 'cancel',
                     'peer-exit', 'helper-stall', 'authority-restart', 'duplicate-pending', 'bad-sequence'):
            if case in ('valid', 'cancel'):
                rule(True)
                run('systemctl', 'restart', 'polkit.service')
            with tempfile.TemporaryDirectory(prefix='niayan-operator-') as temporary:
                directory = Path(temporary)
                directory.chmod(0o755)
                peer = Peer(directory, account.pw_uid, account.pw_gid)
                guard = None
                try:
                    if case == 'bad-sequence':
                        result = subprocess.run([module.HELPER, str(peer.peer.fileno()), PLAN.decode(), REQUEST.decode(),
                            str(module.now_ms()+5000), '--noninteractive'], pass_fds=(peer.peer.fileno(),),
                            input=struct.pack('>Q', 2), capture_output=True, timeout=8)
                        assert result.returncode == 2 and not result.stdout
                    else:
                        plan = bytes([0x33])*32 if case == 'wrong-plan' else bytes.fromhex(PLAN.decode())
                        try:
                            guard = module.OperatorGuard(peer.peer, plan, bytes.fromhex(REQUEST.decode()),
                                module.now_ms()+10_000, interactive=False)
                        except module.Rejected:
                            assert case in ('default-deny', 'wrong-plan')
                            os.fstat(peer.peer.fileno())
                            passed.append(case)
                            print('PASS', case, flush=True)
                            continue
                        if case in ('default-deny', 'wrong-plan'):
                            refusal(lambda: observe(guard))
                        elif case == 'stale-first-reply':
                            guard.request_check()
                            pending = select.poll()
                            pending.register(guard.child.stdout.fileno(), select.POLLIN)
                            assert pending.poll(5000)
                            time.sleep(module.CHECK_MS/1000 + .1)
                            refusal(guard.receive)
                        elif case == 'duplicate-pending':
                            guard.request_check()
                            refusal(guard.request_check)
                        else:
                            first = observe(guard)
                            assert first.sequence == 1
                            if case == 'valid':
                                second = observe(guard)
                                assert second.sequence == 2 and second.started >= first.finished
                                refusal(guard.receive)  # A result cannot be read twice.
                            elif case == 'rule-change':
                                rule(False)
                                deadline = time.monotonic()+5
                                while True:
                                    try:
                                        observe(guard)
                                    except module.Rejected:
                                        break
                                    if time.monotonic() > deadline:
                                        raise AssertionError('rule change was not observed')
                                    time.sleep(.05)
                            elif case == 'cancel':
                                peer.cancel()
                                refusal(guard.request_check)
                            elif case == 'peer-exit':
                                peer.disconnect()
                                refusal(guard.request_check)
                            elif case == 'authority-restart':
                                run('systemctl', 'restart', 'polkit.service')
                                refusal(lambda: observe(guard))
                            elif case == 'helper-stall':
                                os.kill(guard.child.pid, signal.SIGSTOP)
                                guard.request_check()
                                started = time.monotonic()
                                refusal(lambda: wait_pending(guard))
                                assert time.monotonic()-started < 3
                        assert guard.phase is module.Phase.FAILED
                        refusal(guard.request_check)
                        pidfd = os.pidfd_open(guard.child.pid)
                        try:
                            guard.close()
                            poll = select.poll()
                            poll.register(pidfd, select.POLLIN)
                            assert poll.poll(1000)
                        finally:
                            os.close(pidfd)
                        os.fstat(peer.peer.fileno())
                finally:
                    if guard is not None:
                        guard.close()
                    peer.close()
            passed.append(case)
            print('PASS', case, flush=True)
    finally:
        if RULE.exists():
            RULE.unlink()
            run('systemctl', 'restart', 'polkit.service')
    args.report.write_text(json.dumps(dict(result='pass',cases=passed,test_rule_removed=not RULE.exists(),
        actual_native_polkit=True,authentication_dialog_exercised=False,exact_plan_consent=False,
        physical_effects=False,whole_runtime_proof=False),indent=2)+'\n')


if __name__ == '__main__':
    main()
