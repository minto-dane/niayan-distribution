#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Cancel an actual running worker in an explicitly provisioned disposable VM."""
import argparse
import array
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import tarfile
import time

sys.path.insert(0, '/usr/libexec/niaos')
from root_bank import canonical
from storage_bootstrap import check_bank


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable-vm', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    assert __debug__ and os.getuid() == os.geteuid() == 0
    assert subprocess.check_output(['systemd-detect-virt'], timeout=5).strip() in (b'kvm', b'qemu')
    base = Path('/var/lib/niaos')
    bank = base / 'roots'
    assert not (base / 'root-session.json').exists()
    assert set(p.name for p in bank.iterdir()) == {'bank.json', 'bank.lock'}
    assert check_bank()['readonly']
    source = args.report.parent / 'cancel.tar'
    with tarfile.open(source, 'w', format=tarfile.USTAR_FORMAT) as archive:
        directory = tarfile.TarInfo('.')
        directory.type = tarfile.DIRTYPE
        directory.mode = 0o755
        archive.addfile(directory)
        item = tarfile.TarInfo('payload')
        item.size = 32 * 1024 * 1024
        archive.addfile(item, io.BytesIO(bytes(item.size)))
    source.chmod(0o444)
    unit = 'niaos-root-session.service'
    subprocess.run(['systemctl', 'start', 'niaos-root-session.socket', unit], check=True, timeout=15)
    controller = int(subprocess.check_output(['systemctl', 'show', unit, '--property=MainPID', '--value'], timeout=5))
    controller_fd = os.pidfd_open(controller)
    archive_fd = os.open(source, os.O_RDONLY | os.O_CLOEXEC)
    lease = os.open(base / 'core/store/store.lock', os.O_RDWR | os.O_CLOEXEC)
    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    peer = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    peer.settimeout(8)
    worker_fd = -1
    try:
        peer.connect('/run/niaos/root-session.sock')
        request = dict(version=1, stage='4'*32, generation='5'*64, root_manifest='6'*64,
                       archive=hashlib.sha256(source.read_bytes()).hexdigest(), size=source.stat().st_size,
                       entries=2, deadline_ms=int(time.clock_gettime(time.CLOCK_BOOTTIME)*1000)+60000)
        message = dict(version=1, operation='prepare-freeze', request=request,
                       worker_sha256=hashlib.sha256(Path('/usr/libexec/niaos/root-extract').read_bytes()).hexdigest(),
                       device_plan_sha256=hashlib.sha256(Path('/etc/niaos/root-bank-device.json').read_bytes()).hexdigest(),
                       boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), bank=check_bank()['identity'])
        peer.sendmsg([canonical(message)], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', (archive_fd, lease)))])
        until = time.monotonic()+5
        while time.monotonic() < until:
            # Only descendants of the pinned controller created for this test.
            children = Path(f'/proc/{controller}/task/{controller}/children').read_text().split()
            for child in children:
                try:
                    descendants = Path(f'/proc/{child}/task/{child}/children').read_text().split()
                    for descendant in descendants:
                        if os.readlink(f'/proc/{descendant}/exe') != '/usr/libexec/niaos/root-extract':
                            continue
                        worker_fd = os.pidfd_open(int(descendant))
                        signal.pidfd_send_signal(worker_fd, signal.SIGSTOP)
                        for _ in range(100):
                            state = Path(f'/proc/{descendant}/status').read_text()
                            if '\nState:\tT' in state:
                                break
                            time.sleep(.001)
                        else:
                            raise AssertionError('native worker did not stop')
                        break
                except FileNotFoundError:
                    continue
                if worker_fd >= 0:
                    break
            if worker_fd >= 0:
                break
            time.sleep(.001)
        assert worker_fd >= 0, 'native worker boundary not observed'
        assert (bank / request['stage'] / 'intent.json').exists()
        assert not os.statvfs(bank).f_flag & os.ST_RDONLY
        attempt = (base / 'root-session.json').read_bytes()
        started = time.monotonic()
        peer.close()
        exited = select.poll()
        exited.register(worker_fd, select.POLLIN)
        assert exited.poll(5000), 'cancelled native worker still executing'
        completion = base / 'root-session-complete.json'
        for _ in range(500):
            if completion.exists():
                break
            time.sleep(.01)
        result = json.loads(completion.read_bytes())
        assert result['bank_readonly'] and not result['published'] and not result['boot_authorized']
        assert check_bank()['readonly'] and (base / 'root-session.json').read_bytes() == attempt
        # Preserve the original first-use barrier, including after disconnect.
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as retry:
            retry.settimeout(5)
            retry.connect('/run/niaos/root-session.sock')
            retry.sendmsg([canonical(message)], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', (archive_fd, lease)))])
            assert json.loads(retry.recv(4096))['state'] == 'refused-or-indeterminate'
        assert (base / 'root-session.json').read_bytes() == attempt
        args.report.write_text(json.dumps(dict(result='pass', stopped_native_worker_cancelled=True,
            cancellation_seconds=time.monotonic()-started, completion=result,
            bank_readonly=True, retry_refused=True, attempt_sha256=hashlib.sha256(attempt).hexdigest(),
            whole_runtime_proof=False, production_authorization=False), indent=2)+'\n')
    finally:
        peer.close()
        if worker_fd >= 0:
            try:
                signal.pidfd_send_signal(worker_fd, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.close(worker_fd)
        os.close(archive_fd)
        os.close(lease)
        os.close(controller_fd)


if __name__ == '__main__':
    main()
