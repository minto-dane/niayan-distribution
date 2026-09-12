#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Shared bank invariants and process loss in an explicitly disposable VM."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import root_bank
from root_bank import Bank, Rejected, canonical, provision_bank
from check_root_extract import archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', required=True, type=Path)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    assert os.getuid() == os.geteuid() == 0, 'disposable privileged VM required'
    results = {}
    with tempfile.TemporaryDirectory(prefix='bank-test-', dir=args.base) as temporary:
        base = Path(temporary)
        bank_path = base/'bank'; bank_path.mkdir(mode=0o700)
        lease_path = base/'cas.lock'; lease_path.touch(mode=0o600); os.chown(lease_path, 1000, 1000)
        wrong_path = base/'wrong.lock'; wrong_path.touch(mode=0o600); os.chown(wrong_path, 1000, 1000)
        raw, entries = archive(); source = base/'root.tar'; source.write_bytes(raw); source.chmod(0o444)
        provision_bank(bank_path)
        source_fd = os.open(source, os.O_RDONLY)
        lease_fd = os.open(lease_path, os.O_RDWR)
        wrong_fd = os.open(wrong_path, os.O_RDWR)
        fcntl.flock(lease_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        request = dict(version=1, stage='1'*32, generation='2'*64, root_manifest='3'*64,
                       archive=hashlib.sha256(raw).hexdigest(), size=len(raw), entries=entries,
                       deadline_ms=int(time.clock_gettime(time.CLOCK_BOOTTIME)*1000)+60000)
        bank = Bank(bank_path, lease_path, args.worker, 1000)
        try:
            try: bank.prepare(request, source_fd, wrong_fd)
            except Rejected: results['wrong-reservation'] = True
            else: raise AssertionError('wrong reservation accepted')
            assert not (bank_path/request['stage']).exists()
            try: other = Bank(bank_path, lease_path, args.worker, 1000)
            except BlockingIOError: results['bank-exclusion'] = True
            else: other.close(); raise AssertionError('parallel bank writer accepted')
            result = bank.prepare(request, source_fd, lease_fd)
            assert result['state'] == 'extracted' and result['published'] is False
            saved = [(bank_path/request['stage']/n).read_bytes() for n in ('intent.json', 'result.json')]
            try: bank.prepare(request, source_fd, lease_fd)
            except FileExistsError: results['duplicate-refused'] = True
            else: raise AssertionError('duplicate preparation accepted')
            assert [(bank_path/request['stage']/n).read_bytes() for n in ('intent.json', 'result.json')] == saved
            bank.close(); bank = Bank(bank_path, lease_path, args.worker, 1000)
            result = bank.inspect(request['stage'])
            assert result['state'] == 'extracted' and result['physical_revalidation'] is False
            assert (bank_path/request['stage']/'root/etc/value').read_bytes() == b'value\x00\xff'
            results['prepare-and-reopen'] = True
            bank.close()
            # Stop an owned child after the real intent fsync, before any worker
            # starts. This is a process-loss test, not a storage power-loss model.
            read_end, write_end = os.pipe()
            crash_request = dict(request, stage='5'*32)
            child = os.fork()
            if child == 0:
                os.close(read_end)
                try:
                    original_record = root_bank.new_record
                    def stop_after_intent(directory, name, value):
                        original_record(directory, name, value)
                        if name == 'intent.json':
                            os.write(write_end, b'1')
                            os.kill(os.getpid(), signal.SIGSTOP)
                            raise AssertionError('fault child must not resume')
                    root_bank.new_record = stop_after_intent
                    owned = Bank(bank_path, lease_path, args.worker, 1000)
                    owned.prepare(crash_request, source_fd, lease_fd)
                    os._exit(1)
                except BaseException:
                    import traceback; traceback.print_exc(); os._exit(1)
            os.close(write_end)
            try:
                import select
                assert select.select([read_end], [], [], 10)[0], 'intent barrier timeout'
                assert os.read(read_end, 1) == b'1'
                parent = bank_path/crash_request['stage']
                assert (parent/'intent.json').read_bytes() == canonical(crash_request)
                assert not (parent/'result.json').exists()
                os.kill(child, signal.SIGKILL)
                _, status = os.waitpid(child, 0); child = None
                assert os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL
                bank = Bank(bank_path, lease_path, args.worker, 1000)
                assert bank.inspect(crash_request['stage'])['state'] == 'interrupted'
                try: bank.prepare(crash_request, source_fd, lease_fd)
                except FileExistsError: pass
                else: raise AssertionError('interrupted root silently reused')
                results['durable-intent-process-loss'] = True
                results['interrupted-not-reinitialized'] = True
            finally:
                os.close(read_end)
                if child is not None:
                    os.kill(child, signal.SIGKILL); os.waitpid(child, 0)
            competing = os.open(lease_path, os.O_RDWR)
            try:
                try: fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError: results['caller-reservation-retained'] = True
                else: raise AssertionError('borrowed reservation released')
            finally: os.close(competing)
        finally:
            bank.close()
            for fd in (source_fd, lease_fd, wrong_fd): os.close(fd)
    args.report.write_text(json.dumps(dict(result='pass', cases=results,
        installed_root_changed=False, socket_transport_tested=False,
        native_admission_provider=False, storage_power_loss_tested=False), indent=2)+'\n')
    print('PASS shared root bank, retained reservation, duplicate refusal and process loss')


if __name__ == '__main__':
    main()
