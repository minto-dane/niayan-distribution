# SPDX-License-Identifier: BSD-3-Clause
"""Internal privileged preparation service; never selects an installed root.

Only a configured core UID may submit a previously admitted generation. The
actual CAS lock OFD accompanies the archive FD and remains held by the worker.
No public management command, default authority or package database is added.
"""
import array
import contextlib
import fcntl
import hashlib
import json
import os
import pwd
from pathlib import Path
import re
import socket
import stat
import struct
import subprocess
import time

MAX_PACKET = 4096
HEX = re.compile(r'[0-9a-f]{64}\Z')
STAGE = re.compile(r'[0-9a-f]{32}\Z')
FIELDS = {'version', 'stage', 'generation', 'root_manifest', 'archive', 'size', 'entries', 'deadline_ms'}


class Rejected(ValueError):
    pass


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode()


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise Rejected('duplicate-field')
        value[key] = item
    return value


def decode(raw, *, require_canonical=True):
    if not raw or len(raw) > MAX_PACKET:
        raise Rejected('packet-size')
    value = json.loads(raw, object_pairs_hook=unique)
    if require_canonical and canonical(value) != raw:
        raise Rejected('noncanonical')
    return value


def validate_request(request):
    if type(request) is not dict or set(request) != FIELDS or request['version'] != 1:
        raise Rejected('request-schema')
    if type(request['version']) is not int or not isinstance(request['stage'], str) or not STAGE.fullmatch(request['stage']) or request['stage'] == '0' * 32:
        raise Rejected('request-identity')
    for key in ('generation', 'root_manifest', 'archive'):
        if not isinstance(request[key], str) or not HEX.fullmatch(request[key]) or request[key] == '0' * 64:
            raise Rejected('request-digest')
    for key, maximum in [('size', 8 * 1024**3), ('entries', 524288), ('deadline_ms', 2**63 - 1)]:
        if type(request[key]) is not int or not 1 <= request[key] <= maximum:
            raise Rejected('request-bound')
    if request['size'] < 1024 or request['size'] % 512:
        raise Rejected('archive-size')


def identity(info):
    return info.st_dev, info.st_ino


def private_directory(fd):
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
        raise Rejected('private-directory')
    return info


def mount_identity(fd):
    # Kernel-owned per-descriptor identity; no caller-provided filesystem path.
    with open(f'/proc/self/fdinfo/{fd}', 'rb') as source:
        raw = source.read(4097)
    if len(raw) > 4096:
        raise Rejected('mount-identity')
    values = [line.split(b':', 1)[1].strip() for line in raw.splitlines() if line.startswith(b'mnt_id:')]
    if len(values) != 1 or not values[0].isdigit() or int(values[0]) <= 0:
        raise Rejected('mount-identity')
    return int(values[0])


def protected_mount(fd):
    required = os.ST_NODEV | os.ST_NOSUID | os.ST_NOEXEC
    if os.fstatvfs(fd).f_flag & required != required:
        raise Rejected('mount-policy')


def new_record(directory, name, value):
    # Missing or partial records are never converted into a fresh request.
    raw = canonical(value)
    if len(raw) > MAX_PACKET:
        raise Rejected('record-size')
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
    try:
        position = 0
        while position < len(raw):
            count = os.write(fd, raw[position:])
            if count <= 0:
                raise OSError('short record write')
            position += count
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(directory)


def read_record(directory, name):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=directory)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
            raise Rejected('record-metadata')
        raw = os.read(fd, MAX_PACKET + 1)
        result = decode(raw)
        # Reconcile a complete record after a process-only crash before fsync.
        os.fsync(fd)
        os.fsync(directory)
        return result
    finally:
        os.close(fd)


def provision_bank(path):
    """Explicit protected bootstrap only; serve() never provisions missing state."""
    if os.getuid() or os.geteuid():
        raise Rejected('privilege')
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        private_directory(fd)
        protected_mount(fd)
        if os.listdir(fd):
            raise Rejected('bank-not-empty')
        new_record(fd, 'bank.json', {'version': 1, 'purpose': 'inactive-root-preparation'})
        lock = os.open('bank.lock', os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd)
        os.fsync(lock)
        os.close(lock)
        os.fsync(fd)
    finally:
        os.close(fd)


class Bank:
    def __init__(self, path, reservation_path, worker, client_uid, *, inherited_lock=None):
        if os.getuid() or os.geteuid() or type(client_uid) is not int or client_uid <= 0:
            raise Rejected('privilege')
        self.directory = self.lock = self.reservation = self.worker_fd = -1
        self.client_uid, self.worker = client_uid, str(Path(worker).resolve(strict=True))
        try:
            self.worker_fd = os.open(self.worker, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
            wi = os.fstat(self.worker_fd)
            if not stat.S_ISREG(wi.st_mode) or wi.st_uid or wi.st_mode & 0o022:
                raise Rejected('worker-protection')
            if not 0 < wi.st_size <= 16 * 1024**2:
                raise Rejected('worker-size')
            self.worker_hash = hashlib.sha256(os.pread(self.worker_fd, wi.st_size + 1, 0)).hexdigest()
            self.directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            private_directory(self.directory)
            protected_mount(self.directory)
            self.lock = os.open('bank.lock', os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=self.directory)
            info = os.fstat(self.lock)
            if not stat.S_ISREG(info.st_mode) or info.st_uid or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
                raise Rejected('bank-lock')
            if inherited_lock is not None:
                # A private supervisor may share its already held bank OFD with
                # a worker whose capability bounding set has been reduced.
                held = os.fstat(inherited_lock)
                if (identity(held) != identity(info) or held.st_uid or held.st_nlink != 1
                        or stat.S_IMODE(held.st_mode) != 0o600
                        or fcntl.fcntl(inherited_lock, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY):
                    raise Rejected('inherited-bank-reservation')
                duplicate = fcntl.fcntl(inherited_lock, fcntl.F_DUPFD_CLOEXEC, 3)
                os.close(self.lock); self.lock = duplicate
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if read_record(self.directory, 'bank.json') != {'version': 1, 'purpose': 'inactive-root-preparation'}:
                raise Rejected('bank-format')
            self.reservation = os.open(reservation_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
            ri = os.fstat(self.reservation)
            if not stat.S_ISREG(ri.st_mode) or ri.st_uid != client_uid or ri.st_nlink != 1 or ri.st_size != 0 or stat.S_IMODE(ri.st_mode) != 0o600:
                raise Rejected('reservation-policy')
        except BaseException:
            self.close()
            raise

    def close(self):
        for key in ('worker_fd', 'reservation', 'lock', 'directory'):
            fd = getattr(self, key, -1)
            if fd >= 0:
                os.close(fd)
                setattr(self, key, -1)

    def check_inputs(self, request, archive_fd, lease_fd):
        expected, lease = os.fstat(self.reservation), os.fstat(lease_fd)
        if lease.st_uid != self.client_uid or stat.S_IMODE(lease.st_mode) != 0o600 or lease.st_size != 0 or identity(expected) != identity(lease) or expected.st_nlink != 1 or lease.st_nlink != 1 or fcntl.fcntl(lease_fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDWR:
            raise Rejected('reservation-identity')
        fcntl.flock(lease_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Never LOCK_UN: descriptors received via SCM_RIGHTS share the caller's OFD.
        source = os.fstat(archive_fd)
        if not stat.S_ISREG(source.st_mode) or source.st_size != request['size'] or fcntl.fcntl(archive_fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY:
            raise Rejected('archive-descriptor')

    def verify(self, request, archive_fd, lease_fd):
        """Fresh inspection of an already extracted, independently read-only root.

        The caller supplies newly admitted bindings and a finite current deadline.
        This returns a point-in-time observation, not a durable publication permit.
        No intent/result is rewritten and no interrupted extraction is resumed.
        """
        validate_request(request)
        remaining = (request['deadline_ms'] - time.clock_gettime(time.CLOCK_BOOTTIME) * 1000) / 1000
        if not 0 < remaining <= 600:
            raise Rejected('deadline')
        self.check_inputs(request, archive_fd, lease_fd)
        stage = request['stage']
        result = self.inspect(stage)
        if result['state'] != 'extracted' or result['worker_sha256'] != self.worker_hash:
            raise Rejected('extracted-worker-binding')
        parent = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.directory)
        try:
            private_directory(parent)
            intent = read_record(parent, 'intent.json')
            if any(request[key] != intent[key] for key in FIELDS - {'deadline_ms'}):
                raise Rejected('verification-binding')
            target = os.open('root', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            try:
                protected_mount(target)
                if not os.fstatvfs(target).f_flag & os.ST_RDONLY:
                    raise Rejected('read-only-root')
                before = os.fstat(target)
                args = [self.worker, request['archive'], str(request['size']), str(request['entries']), str(request['deadline_ms']),
                        str(archive_fd), str(parent), str(lease_fd), '--verify']
                child = subprocess.Popen(args, executable=f'/proc/self/fd/{self.worker_fd}',
                    pass_fds=(archive_fd, parent, lease_fd, self.worker_fd), stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C.UTF-8'})
                try:
                    stdout, stderr = child.communicate(timeout=remaining + 1)
                except BaseException:
                    child.kill(); child.communicate(); raise
                if child.returncode or stderr or len(stdout) > MAX_PACKET:
                    raise Rejected('physical-verification')
                observed = json.loads(stdout, object_pairs_hook=unique)
                expected = {'result': 'verified', 'profile': 'linux-inode-v1', 'archive_sha256': request['archive'],
                    'entries': request['entries'], 'published': False, 'inode': before.st_ino,
                    'device_major': os.major(before.st_dev), 'device_minor': os.minor(before.st_dev),
                    'mount_id': mount_identity(target)}
                if type(observed) is not dict or set(observed) != set(expected) or any(
                    type(observed[key]) is not type(value) or observed[key] != value for key, value in expected.items()
                ) or type(observed['mount_id']) is not int or observed['mount_id'] <= 0:
                    raise Rejected('verification-response')
                # Keep an FD to the inspected tree and reject a changed entry or
                # accepted extraction record before returning the observation.
                current = os.open('root', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
                try:
                    unchanged = identity(os.fstat(current)) == identity(before) and mount_identity(current) == expected['mount_id']
                    protected_mount(current)
                    unchanged = unchanged and bool(os.fstatvfs(current).f_flag & os.ST_RDONLY)
                finally:
                    os.close(current)
                self.check_inputs(request, archive_fd, lease_fd)
                if not unchanged or self.inspect(stage) != result:
                    raise Rejected('verification-changed')
                if request['deadline_ms'] <= time.clock_gettime(time.CLOCK_BOOTTIME) * 1000:
                    raise Rejected('deadline')
                return dict(result, physical_revalidation=True, observation=observed,
                    verification_deadline_ms=request['deadline_ms'])
            finally:
                os.close(target)
        finally:
            os.close(parent)

    def prepare(self, request, archive_fd, lease_fd):
        validate_request(request)
        now = int(time.clock_gettime(time.CLOCK_BOOTTIME) * 1000)
        if request['size'] < 1024 or request['size'] % 512 or not 0 < request['deadline_ms'] - now <= 600000:
            raise Rejected('deadline-or-size')
        self.check_inputs(request, archive_fd, lease_fd)
        stage = request['stage']
        os.mkdir(stage, mode=0o700, dir_fd=self.directory)
        os.fsync(self.directory)
        parent = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.directory)
        try:
            new_record(parent, 'intent.json', request)
            os.mkdir('root', mode=0o700, dir_fd=parent)
            os.fsync(parent)
            remaining = (request['deadline_ms'] - time.clock_gettime(time.CLOCK_BOOTTIME) * 1000) / 1000
            if remaining <= 0:
                raise Rejected('deadline')
            args = [self.worker, request['archive'], str(request['size']), str(request['entries']), str(request['deadline_ms']),
                    str(archive_fd), str(parent), str(lease_fd)]
            # No shell/preexec callback; the worker maps explicit inherited FDs.
            child = subprocess.Popen(args, executable=f'/proc/self/fd/{self.worker_fd}', pass_fds=(archive_fd, parent, lease_fd, self.worker_fd), stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C.UTF-8'})
            try:
                stdout, stderr = child.communicate(timeout=remaining + 1)
            except BaseException:
                child.kill()
                child.communicate()
                raise
            if len(stdout) > MAX_PACKET or len(stderr) > MAX_PACKET:
                raise Rejected('worker-output')
            # Protected, bounded diagnostics are not a terminal success record.
            new_record(parent, 'worker.json', {
                'version': 1, 'exit': child.returncode,
                'stdout': stdout[:512].decode('utf-8', errors='replace'),
                'stderr': stderr[:512].decode('utf-8', errors='replace'),
                'truncated': len(stdout) > 512 or len(stderr) > 512})
            wanted = {'result': 'extracted', 'profile': 'linux-inode-v1', 'archive_sha256': request['archive'],
                      'entries': request['entries'], 'published': False}
            success = child.returncode == 0 and not stderr and json.loads(stdout, object_pairs_hook=unique) == wanted
            result = {'version': 1, 'intent_sha256': hashlib.sha256(canonical(request)).hexdigest(),
                      'state': 'extracted' if success else 'failed', 'worker_exit': child.returncode, 'worker_sha256': self.worker_hash,
                      'published': False, 'effects_applied': False}
            new_record(parent, 'result.json', result)
            return result
        finally:
            os.close(parent)

    def inspect(self, stage):
        if not isinstance(stage, str) or not STAGE.fullmatch(stage):
            raise Rejected('stage')
        parent = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.directory)
        try:
            private_directory(parent)
            intent = read_record(parent, 'intent.json')
            validate_request(intent)
            if intent['stage'] != stage:
                raise Rejected('intent-binding')
            try:
                result = read_record(parent, 'result.json')
            except FileNotFoundError:
                return {'state': 'interrupted', 'published': False, 'physical_revalidation': False}
            if type(result) is not dict or set(result) != {'version', 'intent_sha256', 'state', 'worker_exit', 'worker_sha256', 'published', 'effects_applied'} or type(result.get('version')) is not int or result.get('version') != 1 or result.get('state') not in ('extracted', 'failed') or type(result.get('worker_exit')) is not int or result.get('published') is not False or result.get('effects_applied') is not False or result.get('intent_sha256') != hashlib.sha256(canonical(intent)).hexdigest():
                raise Rejected('result-binding')
            if not isinstance(result['worker_sha256'], str) or not HEX.fullmatch(result['worker_sha256']) or (result['state'] == 'extracted' and result['worker_exit'] != 0):
                raise Rejected('worker-binding')
            return dict(result, physical_revalidation=False)
        finally:
            os.close(parent)

    def connection(self, peer):
        descriptors = []
        try:
            _, uid, _ = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != self.client_uid:
                raise Rejected('peer')
            peer.settimeout(2)
            raw, controls, flags, _ = peer.recvmsg(MAX_PACKET, socket.CMSG_SPACE(8), socket.MSG_CMSG_CLOEXEC)
            invalid_control = False
            for level, kind, data in controls:
                if level != socket.SOL_SOCKET or kind != socket.SCM_RIGHTS:
                    invalid_control = True
                    continue
                values = array.array('i')
                invalid_control |= bool(len(data) % values.itemsize)
                values.frombytes(data[:len(data) - len(data) % values.itemsize])
                descriptors.extend(values)
            if invalid_control:
                raise Rejected('control')
            if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
                raise Rejected('truncated')
            request = decode(raw)
            if type(request) is dict and set(request) == {'inspect'} and not descriptors:
                result = self.inspect(request['inspect'])
            elif type(request) is dict and set(request) == {'verify'} and len(descriptors) == 2:
                result = self.verify(request['verify'], *descriptors)
            elif len(descriptors) == 2:
                result = self.prepare(request, *descriptors)
            else:
                raise Rejected('descriptors')
            peer.sendall(canonical(result))
        except (OSError, ValueError, subprocess.SubprocessError):
            with contextlib.suppress(OSError):
                peer.sendall(canonical({'state': 'refused-or-indeterminate', 'published': False}))
        finally:
            for fd in descriptors:
                os.close(fd)
            peer.close()

    def serve(self, listener, *, requests=None):
        if listener.family != socket.AF_UNIX or listener.type != socket.SOCK_SEQPACKET:
            raise Rejected('listener')
        count = 0
        while requests is None or count < requests:
            peer, _ = listener.accept()
            self.connection(peer)
            count += 1


def read_policy(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
            raise Rejected('policy-protection')
        policy = decode(os.read(fd, MAX_PACKET + 1), require_canonical=False)
    finally:
        os.close(fd)
    if type(policy) is not dict or type(policy.get('version')) is not int:
        raise Rejected('policy-schema')
    identity_key = {1: 'client_uid', 2: 'client_user'}.get(policy['version'])
    if identity_key is None or set(policy) != {'version', 'bank', 'reservation', 'worker', identity_key}:
        raise Rejected('policy-schema')
    for key in ('bank', 'reservation', 'worker'):
        if type(policy[key]) is not str or not policy[key].startswith('/') or '\x00' in policy[key]:
            raise Rejected('policy-path')
    if identity_key == 'client_user':
        name = policy['client_user']
        if not isinstance(name, str) or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', name):
            raise Rejected('policy-account')
        policy['client_uid'] = pwd.getpwnam(name).pw_uid
    if type(policy['client_uid']) is not int or policy['client_uid'] <= 0:
        raise Rejected('policy-account')
    return policy


def main():
    """Internal daemon or explicit bootstrap; neither initializes a CAS."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--provision-bank', action='store_true')
    args = parser.parse_args()
    if os.getuid() or os.geteuid():
        raise Rejected('privilege')
    policy = read_policy(args.config)
    if args.provision_bank:
        # Existing empty protected mount only, explicitly requested by installer.
        # Never recreate or initialize the independently owned native CAS.
        provision_bank(policy['bank'])
        bank = Bank(policy['bank'], policy['reservation'], policy['worker'], policy['client_uid'])
        bank.close()
        return
    if os.environ.get('LISTEN_PID') != str(os.getpid()) or os.environ.get('LISTEN_FDS') != '1':
        raise Rejected('activation')
    listener = socket.socket(fileno=3)
    bank = Bank(policy['bank'], policy['reservation'], policy['worker'], policy['client_uid'])
    try:
        bank.serve(listener)
    finally:
        bank.close()
        listener.close()


if __name__ == '__main__':
    main()
