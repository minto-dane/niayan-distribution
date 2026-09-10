#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise actual peer credentials, FD passing, worker and persistent bank."""
import argparse
import array
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from root_bank import Bank, canonical, provision_bank
from check_root_extract import archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', required=True, type=Path)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    if os.getuid() != 0 or os.geteuid() != 0:
        parser.error('requires a disposable privileged VM')
    with tempfile.TemporaryDirectory(prefix='bank-test-', dir=args.base) as tmp:
        base = Path(tmp)
        base.chmod(0o711)
        bank_path = base / 'bank'; bank_path.mkdir(mode=0o700)
        client_path = base / 'client'; client_path.mkdir(mode=0o700); os.chown(client_path, 1000, 1000)
        lease_path = client_path / 'cas.lock'; lease_path.touch(mode=0o600); os.chown(lease_path, 1000, 1000)
        fake_path = client_path / 'wrong.lock'; fake_path.touch(mode=0o600); os.chown(fake_path, 1000, 1000)
        raw, entries = archive(); source = client_path / 'root.tar'; source.write_bytes(raw); source.chmod(0o444)
        provision_bank(bank_path)
        address = str(base / 'broker.sock')
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET); listener.bind(address); listener.listen(8)
        os.chown(address, 1000, 1000); os.chmod(address, 0o600)
        ready_r, ready_w = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(ready_r)
            try:
                bank = Bank(bank_path, lease_path, args.worker, 1000)
                os.write(ready_w, b'1'); os.close(ready_w)
                bank.serve(listener, requests=5)
                bank.close(); os._exit(0)
            except BaseException:
                import traceback; traceback.print_exc(); os._exit(1)
        os.close(ready_w); assert os.read(ready_r, 1) == b'1'; os.close(ready_r); listener.close()
        request = {'version': 1, 'stage': '1' * 32, 'generation': '2' * 64, 'root_manifest': '3' * 64,
                   'archive': hashlib.sha256(raw).hexdigest(), 'size': len(raw), 'entries': entries,
                   'deadline_ms': int(time.clock_gettime(time.CLOCK_BOOTTIME) * 1000) + 60000}
        # Each client drops to the real configured UID, not a claimed JSON UID.
        def rpc(message, *, wrong=False, root=False, pass_descriptors=True):
            read_end, write_end = os.pipe(); child = os.fork()
            if child == 0:
                os.close(read_end)
                try:
                    if not root:
                        os.setgroups([]); os.setgid(1000); os.setuid(1000)
                    peer = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET); peer.connect(address)
                    if pass_descriptors:
                        source_fd = os.open(source, os.O_RDONLY)
                        lease_fd = os.open(fake_path if wrong else lease_path, os.O_RDWR)
                        fcntl.flock(lease_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        before = os.fstat(lease_fd)
                        peer.sendmsg([canonical(message)], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [source_fd, lease_fd]))])
                    elif not root:
                        peer.sendall(canonical(message))
                    # Unauthorized peers are rejected before a request is read.
                    try:
                        result = peer.recv(4096)
                    except ConnectionResetError:
                        if not root: raise
                        result = b''
                    if root and not result:
                        result = canonical({'state': 'refused-or-indeterminate', 'transport': 'closed'})
                    if pass_descriptors:
                        # The service must not unlock the caller's shared OFD.
                        competing = os.open(fake_path if wrong else lease_path, os.O_RDWR)
                        try:
                            try: fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            except BlockingIOError: pass
                            else: raise AssertionError('caller reservation was released')
                        finally: os.close(competing)
                        assert os.fstat(lease_fd).st_size == before.st_size == 0
                    os.write(write_end, result); os._exit(0)
                except BaseException:
                    import traceback; traceback.print_exc(); os._exit(1)
            os.close(write_end)
            result = os.read(read_end, 4096); os.close(read_end)
            _, status = os.waitpid(child, 0); assert status == 0
            return json.loads(result)
        results = {}
        try:
            results['unauthorized-peer'] = rpc({'inspect': request['stage']}, root=True, pass_descriptors=False)
            results['wrong-reservation'] = rpc(request, wrong=True)
            results['prepare'] = rpc(request)
            assert results['prepare']['state'] == 'extracted', results
            results['duplicate'] = rpc(request)
            results['inspect'] = rpc({'inspect': request['stage']}, pass_descriptors=False)
            for key in ('unauthorized-peer', 'wrong-reservation', 'duplicate'):
                assert results[key]['state'] == 'refused-or-indeterminate', results
            assert results['inspect']['state'] == 'extracted' and results['inspect']['physical_revalidation'] is False
            _, status = os.waitpid(pid, 0); pid = None; assert status == 0
            value = bank_path / request['stage'] / 'root/etc/value'
            assert value.read_bytes() == b'value\x00\xff'
            bank = Bank(bank_path, lease_path, args.worker, 1000)
            try:
                results['restart'] = bank.inspect(request['stage'])
                assert results['restart']['state'] == 'extracted'
                # A durable intent without a terminal result stays interrupted.
                interrupted = bank_path / ('4' * 32); interrupted.mkdir(mode=0o700)
                data = dict(request, stage='4' * 32)
                from root_bank import new_record
                d = os.open(interrupted, os.O_RDONLY | os.O_DIRECTORY)
                new_record(d, 'intent.json', data); os.close(d)
                results['interrupted'] = bank.inspect(data['stage'])
                assert results['interrupted']['state'] == 'interrupted'
            finally: bank.close()
            # Kill an actual service after a durable intent becomes visible.
            # No successful terminal result may be inferred after disconnect.
            crash_listener = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            os.unlink(address); crash_listener.bind(address); crash_listener.listen(1)
            os.chown(address, 1000, 1000); os.chmod(address, 0o600)
            crash_ready_r, crash_ready_w = os.pipe()
            crash_pid = os.fork()
            if crash_pid == 0:
                os.close(crash_ready_r)
                service = Bank(bank_path, lease_path, args.worker, 1000)
                os.write(crash_ready_w, b'1'); os.close(crash_ready_w)
                service.serve(crash_listener, requests=1); os._exit(0)
            os.close(crash_ready_w); assert os.read(crash_ready_r, 1) == b'1'; os.close(crash_ready_r)
            crash_listener.close()
            crash_request = dict(request, stage='5' * 32)
            crash_client = os.fork()
            if crash_client == 0:
                os.setgroups([]); os.setgid(1000); os.setuid(1000)
                a = os.open(source, os.O_RDONLY); lock = os.open(lease_path, os.O_RDWR)
                fcntl.flock(lock, fcntl.LOCK_EX)
                peer = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET); peer.connect(address)
                peer.sendmsg([canonical(crash_request)], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [a, lock]))])
                try: response = peer.recv(4096)
                except ConnectionResetError: response = b''
                os._exit(0 if not response else 1)
            interrupted_path = bank_path / crash_request['stage']
            deadline = time.monotonic() + 5
            try:
                while True:
                    try: ready = (interrupted_path / 'intent.json').read_bytes() == canonical(crash_request)
                    except FileNotFoundError: ready = False
                    if ready: break
                    if time.monotonic() >= deadline: raise TimeoutError('intent creation')
                    time.sleep(0.0005)
                # Stop after the complete intent is visible; kill only the owned process.
                os.kill(crash_pid, signal.SIGSTOP)
                assert not (interrupted_path / 'result.json').exists(), 'fault point was missed'
                os.kill(crash_pid, signal.SIGKILL)
                _, status = os.waitpid(crash_pid, 0); crash_pid = None
                assert os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL
                _, status = os.waitpid(crash_client, 0); crash_client = None; assert status == 0
                service = Bank(bank_path, lease_path, args.worker, 1000)
                try:
                    results['service-killed'] = service.inspect(crash_request['stage'])
                    assert results['service-killed']['state'] == 'interrupted'
                finally: service.close()
            finally:
                for owned in (crash_pid, crash_client):
                    if owned is not None:
                        os.kill(owned, signal.SIGKILL); os.waitpid(owned, 0)
            args.report.write_text(json.dumps({'result': 'pass', 'cases': results, 'storage': 'caller-specified mount',
                'installed_root_changed': False, 'native_admission_provider': False}, indent=2) + '\n')
            print('PASS actual root bank peer/FD/worker, retained reservation and restart')
        finally:
            if pid is not None:
                os.kill(pid, signal.SIGKILL); os.waitpid(pid, 0)


if __name__ == '__main__':
    main()
