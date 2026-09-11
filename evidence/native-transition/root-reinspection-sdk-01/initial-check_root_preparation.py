#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Disposable VM integration: native stage admission, real broker and worker.

The Ada driver uses exact artificial fixture authorization, never site policy.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from root_bank import Bank, provision_bank, mount_identity
from check_root_reinspection import snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', type=Path, required=True)
    parser.add_argument('--driver', type=Path, required=True)
    parser.add_argument('--loader', type=Path, required=True)
    parser.add_argument('--libraries', type=Path, required=True)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--configured', action='store_true', help='exercise configured generation driver and source root')
    parser.add_argument('--reinspect', action='store_true', help='exercise reserved native reinspection with an explicit VM freeze provider')
    args = parser.parse_args()
    if os.getuid() or os.geteuid():
        parser.error('requires a disposable privileged VM')
    results = []
    for deny_post in ((False,) if args.reinspect else (False, True)):
        with tempfile.TemporaryDirectory(prefix='prepare-', dir=args.base) as temporary:
            base = Path(temporary); base.chmod(0o711)
            bank_path = base / 'bank'; bank_path.mkdir(mode=0o700)
            client_path = base / 'client'; client_path.mkdir(mode=0o700); os.chown(client_path, 1000, 1000)
            store = client_path / 'store'; store.mkdir(mode=0o700); os.chown(store, 1000, 1000)
            provision_bank(bank_path)
            address = str(base / 'prepare.sock')
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            listener.bind(address); listener.listen(1); listener.settimeout(120)
            os.chown(address, 1000, 1000); os.chmod(address, 0o600)
            command = [str(args.loader), '--library-path', str(args.libraries), str(args.driver),
                str(store), str(args.fixtures), address, hashlib.sha256(args.worker.read_bytes()).hexdigest()]
            if args.configured:
                source = client_path / 'source'; source.mkdir(mode=0o700); os.chown(source, 1000, 1000)
                command.insert(command.index(str(args.fixtures)), str(source))
            if deny_post:
                command.append('deny-post')
            elif args.reinspect:
                command.append('reinspect')
            log_path = args.report.parent / ('native-deny-post.log' if deny_post else 'native-prepare.log')
            bank = None; frozen = None; before = records = None
            with log_path.open('wb') as log:
                child = subprocess.Popen(command, user=1000, group=1000, extra_groups=[],
                    stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                    env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C.UTF-8'})
                try:
                    deadline = time.monotonic() + 120
                    while not (store / 'store.lock').exists():
                        if child.poll() is not None or time.monotonic() >= deadline:
                            raise RuntimeError('native store initialization failed')
                        time.sleep(0.01)
                    bank = Bank(bank_path, store / 'store.lock', args.worker, 1000)
                    bank.serve(listener, requests=1)
                    if args.reinspect:
                        stages = [p for p in bank_path.iterdir() if p.is_dir()]
                        assert len(stages) == 1
                        stage = stages[0]; frozen = stage / 'root'
                        subprocess.run(['mount', '--bind', str(frozen), str(frozen)], check=True)
                        subprocess.run(['mount', '-o', 'remount,bind,ro,nodev,nosuid,noexec', str(frozen)], check=True)
                        before = snapshot(frozen)
                        records = [(stage/n).read_bytes() for n in ('intent.json', 'result.json')]
                        original = json.loads(records[0])['deadline_ms']
                        target_fd = os.open(frozen, os.O_RDONLY | os.O_DIRECTORY)
                        try:
                            info = os.fstat(target_fd)
                            values = (original, mount_identity(target_fd), info.st_ino, os.major(info.st_dev), os.minor(info.st_dev))
                        finally: os.close(target_fd)
                        bridge = client_path / 'frozen-root.pending'
                        bridge.write_text(''.join(str(n)+'\n' for n in values)); os.chown(bridge, 1000, 1000); bridge.chmod(0o600)
                        bridge.rename(client_path / 'frozen-root.txt')
                        bank.serve(listener, requests=5)
                    exit_code = child.wait(timeout=120)
                    if args.reinspect:
                        assert snapshot(frozen) == before
                        assert [(stage/n).read_bytes() for n in ('intent.json', 'result.json')] == records
                    for path in bank_path.glob('*/worker.json'):
                        diagnostic = json.loads(path.read_bytes())
                        print(json.dumps({'post_denied': deny_post, 'worker': diagnostic}), flush=True)
                    assert exit_code == 0, log_path
                    stages = [p for p in bank_path.iterdir() if p.is_dir()]
                    assert len(stages) == 1
                    record = bank.inspect(stages[0].name)
                    assert record['state'] == 'extracted' and record['published'] is False
                    intent = json.loads((stages[0] / 'intent.json').read_bytes())
                    # The actual stage and native root manifests, not detached
                    # fixture hashes, were delivered from the retained context.
                    expected = (client_path / 'archive-stage-state/generation.manifest').read_bytes()
                    assert intent['generation'] == hashlib.sha256(expected).hexdigest()
                    assert expected[:8] == (b'NIAGEN06' if args.configured else b'NIAGEN05')
                    assert len(expected) == (384 if args.configured else 320)
                    offset = 256 if args.configured else 224
                    assert intent['root_manifest'] == expected[offset:offset + 32].hex()
                    if args.configured:
                        address = expected[256:288].hex()
                        saved = (store / 'objects' / address[:2] / address[2:]).read_bytes()
                        assert hashlib.sha256(saved).hexdigest() == address and saved[:8] == b'NIACRT01'
                        assert saved[8:40] == expected[224:256]  # base manifest is retained separately
                        assert saved[184:200] == expected[24:40] and saved[200:232] == expected[160:192]
                        assert saved[264:296].hex() == intent['archive']
                        # The worker extracted the selected empty local file and
                        # preserved incoming content at the admitted backup path.
                        tree = stages[0] / 'root'
                        assert (tree / 'etc/fixture.conf').is_file() and (tree / 'etc/fixture.conf').read_bytes() == b''
                        assert (tree / 'etc/fixture.conf.save').is_file()
                        assert (tree / 'etc/fixture.conf.save').read_bytes() == b'second\n'
                        assert not (source / 'etc/fixture.conf.save').exists()
                        assert (source / 'etc/fixture.conf').read_bytes() == b''
                    assert intent['stage'] == expected[8:24].hex()
                    tar = (client_path / 'archive-stage-root/tree/root.tar').read_bytes()
                    assert intent['archive'] == hashlib.sha256(tar).hexdigest() and intent['size'] == len(tar)
                    results.append({'post_admission_denied': deny_post, 'bank': record, 'intent': intent,
                                    'native_driver_exit': child.returncode, 'actual_peer_and_reservation': True})
                finally:
                    if child.poll() is None:
                        child.kill(); child.wait()
                    if bank is not None:
                        bank.close()
                    if frozen is not None:
                        subprocess.run(['umount', str(frozen)], check=True)
                    listener.close()
    args.report.write_text(json.dumps({'result': 'pass', 'cases': results, 'site_policy': False,
        'configured_generation': args.configured, 'native_reinspection': args.reinspect,
        'frozen_tree_and_records_unchanged': args.reinspect, 'installed_root_changed': False, 'boot_tested': False}, indent=2) + '\n')
    print('PASS native admission and retained archive through actual root preparation service')


if __name__ == '__main__':
    main()
