# SPDX-License-Identifier: BSD-3-Clause
"""Nonblocking root controller client with independently held physical evidence.

Internal root control plane only. The caller independently selects the bank and
admits the scope; neither an RPC response nor this client grants authorization.
The existing controller owns its bank/device reservation until disconnect/EOF.
"""
from __future__ import annotations

import array
from dataclasses import dataclass
from enum import Enum, auto
import hashlib
import json
import os
import socket
import stat
import sys
import uuid

from root_handoff import Rejected, Scope, now_ms

SOCKET = '/run/niaos/root-session.sock'
DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode()


@dataclass(frozen=True)
class RootIdentity:
    mount_id: int
    inode: int
    device_major: int
    device_minor: int

    def fields(self) -> dict[str, int]:
        return dict(mount_id=self.mount_id, inode=self.inode,
                    device_major=self.device_major, device_minor=self.device_minor)

    @classmethod
    def observe(cls, fd: int) -> RootIdentity:
        info = os.fstat(fd)
        required = os.ST_RDONLY | os.ST_NODEV | os.ST_NOSUID | os.ST_NOEXEC
        if not stat.S_ISDIR(info.st_mode) or os.fstatvfs(fd).f_flag & required != required:
            raise Rejected('supervisor-root-mount-policy')
        with open(f'/proc/self/fdinfo/{fd}', 'rb') as source:
            raw = source.read(4097)
        mounts = [line[7:].strip() for line in raw.splitlines() if line.startswith(b'mnt_id:')]
        if len(raw) > 4096 or len(mounts) != 1 or not mounts[0].isdigit() or int(mounts[0]) <= 0:
            raise Rejected('supervisor-mount-identity')
        return cls(int(mounts[0]), info.st_ino, os.major(info.st_dev), os.minor(info.st_dev))


class Phase(Enum):
    NEW = auto()
    PREPARING = auto()
    HELD = auto()
    OBSERVING = auto()
    CLOSING = auto()
    ENDED = auto()
    FAILED = auto()
    CLOSED = auto()


def record(directory: int, name: str) -> bytes:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o600 or not 0 < info.st_size <= 4096):
            raise Rejected('supervisor-record-protection')
        data = os.pread(fd, 4097, 0)
        if len(data) != info.st_size:
            raise Rejected('supervisor-record-size')
        return data
    finally:
        os.close(fd)


def connect() -> socket.socket:
    # Pin protected ancestors while checking the fixed root-only endpoint.
    directory = os.open('/', DIRECTORY)
    peer: socket.socket | None = None
    try:
        for name in ('run', 'niaos'):
            info = os.fstat(directory)
            if info.st_uid or info.st_mode & 0o022:
                raise Rejected('supervisor-socket-directory')
            child = os.open(name, DIRECTORY, dir_fd=directory)
            previous, directory = directory, child
            os.close(previous)
        info = os.fstat(directory)
        endpoint = os.stat('root-session.sock', dir_fd=directory, follow_symlinks=False)
        if (info.st_uid or info.st_mode & 0o022 or not stat.S_ISSOCK(endpoint.st_mode)
                or endpoint.st_uid or stat.S_IMODE(endpoint.st_mode) != 0o600):
            raise Rejected('supervisor-socket-protection')
        peer = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC)
        peer.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        peer.setblocking(False)
        # A full listener queue is a refusal, never a blocking/retrying connect.
        peer.connect(f'/proc/self/fd/{directory}/root-session.sock')
        credentials = peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        if int.from_bytes(credentials[4:8], sys.byteorder, signed=True) != 0:
            raise Rejected('supervisor-controller-owner')
        return peer
    except BaseException:
        if peer is not None:
            peer.close()
        raise
    finally:
        try:
            os.close(directory)
        except BaseException:
            if peer is not None:
                peer.close()
            raise


class RootSession:
    """One prepare, bounded observations, no replay, thaw or deadline renewal.

    Bank FD, scope, device digest and boot ID come from independent selection.
    Input archive/CAS FDs remain borrowed. Abort disconnects immediately; this
    signals the controller's worker monitor but does not certify remote cleanup.
    Only receive() returning True in CLOSING establishes controller EOF.
    """
    def __init__(self, scope: Scope, bank_fd: int, device_plan: bytes, boot_id: str) -> None:
        self.owner = os.getpid()
        self.scope = scope
        self.bank = self.root = -1
        self.peer: socket.socket | None = None
        self.phase = Phase.NEW
        self.sender = 0
        self.identity: RootIdentity | None = None
        self.exchanges = 0
        if (os.getuid() or os.geteuid() or type(scope) is not Scope
                or type(device_plan) is not bytes or len(device_plan) != 32 or not any(device_plan)
                or str(uuid.UUID(boot_id)) != boot_id or not 0 < scope.deadline - now_ms() <= 120_000):
            raise Rejected('supervisor-session-context')
        scope.wire()
        self.device_plan, self.boot_id = device_plan, boot_id
        try:
            self.bank = os.dup(bank_fd)
            self.bank_identity = RootIdentity.observe(self.bank)
            info = os.fstat(self.bank)
            if (info.st_uid or stat.S_IMODE(info.st_mode) != 0o700 or info.st_ino != 2
                    or info.st_dev == os.stat('/').st_dev):
                raise Rejected('supervisor-dedicated-bank')
        except BaseException:
            self.abort()
            raise

    def current(self) -> None:
        if (self.owner != os.getpid() or os.getuid() or os.geteuid()
                or now_ms() >= self.scope.deadline or (self.peer is None and self.phase is not Phase.NEW)
                or self.phase in (Phase.ENDED, Phase.FAILED, Phase.CLOSED)):
            raise Rejected('supervisor-session-ended')

    def descriptor(self) -> int | None:
        self.current()
        return self.peer.fileno() if self.peer is not None else None

    def request(self) -> dict[str, object]:
        s = self.scope
        return dict(version=1, stage=s.stage.hex(), generation=s.generation.hex(),
                    root_manifest=s.root_manifest.hex(), archive=s.archive.hex(),
                    size=s.size, entries=s.entries, deadline_ms=s.deadline)

    def _send(self, value: object, descriptors: tuple[int, ...]) -> None:
        assert self.peer is not None
        raw = canonical(value)
        controls = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', descriptors))] if descriptors else []
        if self.peer.sendmsg([raw], controls, socket.MSG_DONTWAIT | socket.MSG_NOSIGNAL) != len(raw):
            raise Rejected('supervisor-controller-send-indeterminate')

    def prepare(self, archive: int, lease: int) -> None:
        try:
            self.current()
            if self.phase is not Phase.NEW:
                raise Rejected('supervisor-prepare-order')
            # Do not occupy the controller's two-second initial request window
            # while an interactive operator check is pending.
            self.peer = connect()
            self.phase = Phase.PREPARING  # Delivery attempt is terminal on failure.
            self._send(dict(version=1, operation='prepare-freeze', request=self.request(),
                worker_sha256=self.scope.worker.hex(), device_plan_sha256=self.device_plan.hex(),
                boot_id=self.boot_id, bank=self.bank_identity.fields()), (archive, lease))
        except BaseException:
            self.phase = Phase.FAILED
            raise

    def observe(self, archive: int, lease: int) -> None:
        try:
            self.current()
            if self.phase is not Phase.HELD or self.exchanges >= 1200:
                raise Rejected('supervisor-observe-order')
            self.phase = Phase.OBSERVING
            self._send(dict(version=1, operation='observe', stage=self.scope.stage.hex()), (archive, lease))
        except BaseException:
            self.phase = Phase.FAILED
            raise

    def physical(self) -> RootIdentity:
        self.current()
        if RootIdentity.observe(self.bank) != self.bank_identity:
            raise Rejected('supervisor-bank-changed')
        stage = os.open(self.scope.stage.hex(), DIRECTORY, dir_fd=self.bank)
        try:
            info = os.fstat(stage)
            if info.st_uid or stat.S_IMODE(info.st_mode) != 0o700 or info.st_dev != os.fstat(self.bank).st_dev:
                raise Rejected('supervisor-stage-protection')
            fd = os.open('root', DIRECTORY, dir_fd=stage)
            try:
                observed = RootIdentity.observe(fd)
                bank = self.bank_identity
                if (observed.mount_id, observed.device_major, observed.device_minor) != (
                        bank.mount_id, bank.device_major, bank.device_minor):
                    raise Rejected('supervisor-root-outside-bank')
                if self.identity is not None and (observed != self.identity or RootIdentity.observe(self.root) != observed):
                    raise Rejected('supervisor-root-changed')
                intent = canonical(self.request())
                expected = canonical(dict(version=1, intent_sha256=hashlib.sha256(intent).hexdigest(),
                    state='extracted', worker_exit=0, worker_sha256=self.scope.worker.hex(),
                    published=False, effects_applied=False))
                if record(stage, 'intent.json') != intent or record(stage, 'result.json') != expected:
                    raise Rejected('supervisor-physical-record-binding')
                if self.root < 0:
                    self.root, fd = fd, -1
                self.identity = observed
                return observed
            finally:
                if fd >= 0:
                    os.close(fd)
        finally:
            os.close(stage)

    def receive(self) -> bool:
        """False means pending. Evidence is accepted only after physical checks."""
        received: list[int] = []
        try:
            self.current()
            if self.phase not in (Phase.PREPARING, Phase.OBSERVING, Phase.CLOSING):
                raise Rejected('supervisor-receive-order')
            assert self.peer is not None
            try:
                message: tuple[bytes, list[tuple[int, int, bytes]], int, object] = self.peer.recvmsg(
                    4097, socket.CMSG_SPACE(12) + socket.CMSG_SPACE(16 * 4),
                    socket.MSG_DONTWAIT | socket.MSG_CMSG_CLOEXEC)
            except BlockingIOError:
                return False
            raw, controls, flags, _ = message
            credentials: list[tuple[int, int]] = []
            invalid = bool(flags & ~(socket.MSG_CMSG_CLOEXEC | socket.MSG_EOR))
            for level, kind, data in controls:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    values = array.array('i')
                    values.frombytes(data[:len(data) - len(data) % values.itemsize])
                    received.extend(values)
                    invalid = True
                elif level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS and len(data) == 12:
                    credentials.append((int.from_bytes(data[:4], sys.byteorder, signed=True),
                                        int.from_bytes(data[4:8], sys.byteorder, signed=True)))
                else:
                    invalid = True
            if not raw and not controls and not invalid and self.phase is Phase.CLOSING:
                self.phase = Phase.ENDED
                return True
            if (invalid or len(credentials) != 1 or credentials[0][0] <= 0 or credentials[0][1] != 0
                    or self.sender not in (0, credentials[0][0]) or self.phase is Phase.CLOSING):
                raise Rejected('supervisor-controller-sender-or-ancillary')
            self.sender = credentials[0][0]
            observed = self.physical()  # The response does not supply its expected inode.
            expected = canonical(dict(version=1, state='frozen', stage=self.scope.stage.hex(),
                observation=dict(original_deadline_ms=self.scope.deadline, root=observed.fields()),
                deadline_ms=self.scope.deadline, published=False))
            if raw != expected:
                raise Rejected('supervisor-controller-evidence')
            self.current()
            self.exchanges += 1
            self.phase = Phase.HELD
            return True
        except BaseException:
            self.phase = Phase.FAILED
            raise
        finally:
            failures: list[OSError] = []
            for fd in received:
                try:
                    os.close(fd)
                except OSError as error:
                    failures.append(error)
            if failures:
                self.phase = Phase.FAILED
                raise ExceptionGroup('supervisor-unexpected-fd-close', failures)

    def finish(self) -> None:
        try:
            self.current()
            if self.phase is not Phase.HELD:
                raise Rejected('supervisor-close-order')
            self.phase = Phase.CLOSING
            self._send(dict(version=1, operation='close', stage=self.scope.stage.hex()), ())
        except BaseException:
            self.phase = Phase.FAILED
            raise

    def abort(self) -> None:
        # Disconnect FIRST: the controller can stop effects even if local FD
        # release fails. Never unlink records or report this as completed cleanup.
        self.phase = Phase.CLOSED
        peer, self.peer = self.peer, None
        descriptors = (self.root, self.bank)
        self.root = self.bank = -1
        failures: list[OSError] = []
        if peer is not None:
            try:
                peer.close()
            except OSError as error:
                failures.append(error)
        for fd in descriptors:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError as error:
                    failures.append(error)
        if failures:
            raise ExceptionGroup('supervisor-session-close-indeterminate', failures)
