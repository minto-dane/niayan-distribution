# SPDX-License-Identifier: BSD-3-Clause
"""Private worker handoff, without a listener, launcher or automatic execution.

The root supervisor supplies an independently admitted Scope and the actual
unreaped child it launched. Receiving FDs is not admission. It must keep current
operator/supply/consent guards and independently observe the prepared root before
calling complete(). Its controller session outlives this one prepare exchange.
"""
from __future__ import annotations

import array
from dataclasses import dataclass
from enum import Enum, auto
import hashlib
import os
import select
import socket
import struct
import sys
import time

MAX_POLLS = 1200


class Rejected(ValueError):
    pass


def now_ms() -> int:
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME) // 1000000


class Phase(Enum):
    STARTING = auto()
    READY = auto()
    RECEIVING = auto()
    RECEIVED = auto()
    COMPLETING = auto()
    COMPLETE = auto()
    FAILED = auto()
    CLOSED = auto()


class Event(Enum):
    OPEN = auto()
    RECEIVE = auto()
    ACCEPT = auto()
    COMPLETE = auto()
    ACK = auto()
    FAIL = auto()
    CLOSE = auto()


def transition(phase: Phase, event: Event) -> Phase:
    """The runtime's finite control relation; it grants no external authority."""
    if event is Event.CLOSE:
        return Phase.CLOSED
    if event is Event.FAIL and phase not in (Phase.CLOSED, Phase.COMPLETE):
        return Phase.FAILED
    for before, action, after in (
        (Phase.STARTING, Event.OPEN, Phase.READY),
        (Phase.READY, Event.RECEIVE, Phase.RECEIVING),
        (Phase.RECEIVING, Event.ACCEPT, Phase.RECEIVED),
        (Phase.RECEIVED, Event.COMPLETE, Phase.COMPLETING),
        (Phase.COMPLETING, Event.ACK, Phase.COMPLETE),
    ):
        if phase is before and event is action:
            return after
    raise Rejected('invalid-channel-transition')


@dataclass(frozen=True)
class Scope:
    generation: bytes
    root_manifest: bytes
    archive: bytes
    worker: bytes
    stage: bytes
    size: int
    entries: int
    deadline: int

    def wire(self) -> bytes:
        for value, length in [(self.generation, 32), (self.root_manifest, 32),
                              (self.archive, 32), (self.worker, 32), (self.stage, 16)]:
            if type(value) is not bytes or len(value) != length or not any(value):
                raise Rejected('scope-identity')
        if (any(type(value) is not int for value in (self.size, self.entries, self.deadline))
                or not 1024 <= self.size <= 8589934592 or self.size % 512
                or not 1 <= self.entries <= 524288 or not 0 < self.deadline <= 2**63 - 1):
            raise Rejected('scope-bounds')
        return (b'NIAHND01' + self.generation + self.root_manifest + self.archive + self.worker
                + self.stage + struct.pack('>QQQ', self.size, self.entries, self.deadline) + bytes(16))


@dataclass(frozen=True)
class ReinspectionScope(Scope):
    original_deadline: int
    mount_id: int
    inode: int
    device_major: int
    device_minor: int

    def wire(self) -> bytes:
        common = super().wire()
        values = (self.original_deadline, self.mount_id, self.inode, self.device_major, self.device_minor)
        if (any(type(value) is not int for value in values)
                or not 0 < self.original_deadline <= 2**63 - 1
                or not 0 < self.mount_id <= 2**64 - 1 or not 0 < self.inode <= 2**64 - 1
                or not 0 <= self.device_major <= 2**32 - 1 or not 0 <= self.device_minor <= 2**32 - 1):
            raise Rejected('reinspection-identity')
        return (b'NIAHRV01' + common[8:176] + struct.pack('>QQQII', *values) + bytes(16))


class Channel:
    """Own duplicates and received FDs only; never close/reap/kill the caller's child.

    Caller enables SO_PASSCRED on both socketpair ends before spawning the child.
    PID comes from that launch, never a request field. waitid(P_PIDFD, WNOWAIT)
    requires the still-live, unreaped direct child and prevents PID reuse fallback.
    Only its message UID/PID can transfer FDs; descendants cannot impersonate it.
    Single owning process/task; close does not shut down a parent's forked copy.
    """
    def __init__(self, peer: socket.socket, child_pid: int, child_uid: int, scope: Scope) -> None:
        self.peer: socket.socket | None = None
        self.pidfd = -1
        self.descriptors: list[int] = []
        self.phase = Phase.STARTING
        self.owner = os.getpid()
        if (os.getuid() or os.geteuid() or type(child_pid) is not int or child_pid <= 0
                or type(child_uid) is not int or not 0 < child_uid <= 2**31 - 1):
            raise Rejected('supervisor-or-child')
        self.expected = scope.wire()
        self.scope = scope
        self.child_pid, self.child_uid = child_pid, child_uid
        if not 0 < scope.deadline - now_ms() <= 600000:
            raise Rejected('deadline')
        try:
            self.peer = peer.dup()
            if (self.peer.family != socket.AF_UNIX or self.peer.type != socket.SOCK_SEQPACKET
                    or self.peer.getsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED) != 1):
                raise Rejected('private-seqpacket-required')
            self.peer.getpeername()
            self.pidfd = os.pidfd_open(child_pid)
            os.set_inheritable(self.pidfd, False)
            self._alive()
            self._advance(Event.OPEN)
        except BaseException:
            self.close()
            raise

    def _advance(self, event: Event) -> None:
        self.phase = transition(self.phase, event)

    def _peer(self) -> socket.socket:
        peer = self.peer
        if peer is None or self.phase is Phase.CLOSED:
            raise Rejected('channel-closed')
        return peer

    def _alive(self) -> None:
        if self.owner != os.getpid() or os.getuid() or os.geteuid() or now_ms() >= self.scope.deadline:
            raise Rejected('owner-or-deadline')
        if self.pidfd < 0 or os.waitid(os.P_PIDFD, self.pidfd, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None:
            raise Rejected('child-exited')

    def _wait(self, events: int) -> None:
        peer = self._peer()
        for _ in range(MAX_POLLS):
            self._alive()
            poll = select.poll()
            poll.register(peer.fileno(), events)
            poll.register(self.pidfd, select.POLLIN)
            for fd, flags in poll.poll(min(1000, max(1, self.scope.deadline - now_ms()))):
                if fd == self.pidfd or flags & (select.POLLERR | select.POLLHUP | select.POLLNVAL):
                    raise Rejected('child-or-channel-ended')
                if flags & events:
                    return
        raise Rejected('poll-budget-exhausted')

    def receive(self, *, wait: bool = True) -> tuple[int, int]:
        self._advance(Event.RECEIVE)
        try:
            if wait:
                self._wait(select.POLLIN)
            else:
                self._alive()
            # The stdlib stub leaves the unused address untyped. Contain it as
            # object; authentication uses kernel credentials, never that value.
            message: tuple[bytes, list[tuple[int, int, bytes]], int, object] = self._peer().recvmsg(
                len(self.expected) + 1, socket.CMSG_SPACE(12) + socket.CMSG_SPACE(16 * 4),
                socket.MSG_DONTWAIT | socket.MSG_CMSG_CLOEXEC)
            raw, controls, flags, _ = message
            credentials: list[tuple[int, int, int]] = []
            invalid = bool(flags & ~(socket.MSG_CMSG_CLOEXEC | socket.MSG_EOR))
            for level, kind, data in controls:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    values = array.array('i')
                    invalid |= bool(len(data) % values.itemsize)
                    values.frombytes(data[:len(data) - len(data) % values.itemsize])
                    self.descriptors.extend(values)
                elif level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS and len(data) == 12:
                    credentials.append((int.from_bytes(data[0:4], byteorder=sys.byteorder, signed=True),
                                        int.from_bytes(data[4:8], byteorder=sys.byteorder, signed=True),
                                        int.from_bytes(data[8:12], byteorder=sys.byteorder, signed=True)))
                else:
                    invalid = True
            if (invalid or len(credentials) != 1 or credentials[0][0] != self.child_pid
                    or credentials[0][1] != self.child_uid
                    or len(self.descriptors) != 2 or raw != self.expected):
                raise Rejected('sender-scope-or-descriptors')
            self._current()
            self._advance(Event.ACCEPT)
            return self.descriptors[0], self.descriptors[1]
        except BaseException:
            self._advance(Event.FAIL)
            self._release_inputs()
            raise

    def _current(self) -> None:
        self._alive()
        poll = select.poll()
        poll.register(self._peer().fileno(), select.POLLIN)
        if poll.poll(0):
            raise Rejected('cancel-or-disconnect')

    def complete(self, *, wait: bool = True) -> None:
        # Caller has completed its root session request, independent observation
        # and current admission rechecks. No callback is silently supplied here.
        self._advance(Event.COMPLETE)
        try:
            self._release_inputs()
            self._current()
            if wait:
                self._wait(select.POLLOUT)
            self._current()
            opcode = b'NIAHRK01' if isinstance(self.scope, ReinspectionScope) else b'NIAHOK01'
            reply = opcode + hashlib.sha256(self.expected).digest()
            if self._peer().send(reply, socket.MSG_DONTWAIT | socket.MSG_NOSIGNAL) != len(reply):
                raise Rejected('uncertain-reply')
            self._advance(Event.ACK)
        except BaseException:
            self._advance(Event.FAIL)
            raise

    def _release_inputs(self) -> None:
        # Detach before closing. On Linux a close error must not be retried:
        # the numeric FD may already have been reused. Attempt every release.
        descriptors, self.descriptors = self.descriptors, []
        errors: list[OSError] = []
        for fd in descriptors:
            try:
                os.close(fd)
            except OSError as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup('handoff-input-release', errors)

    def close(self) -> None:
        self._advance(Event.CLOSE)
        try:
            self._release_inputs()
        finally:
            pidfd, self.pidfd = self.pidfd, -1
            try:
                if pidfd >= 0:
                    os.close(pidfd)
            finally:
                peer, self.peer = self.peer, None
                if peer is not None:
                    peer.close()

    def __enter__(self) -> Channel:
        return self

    def __exit__(self, *ignored: object) -> None:
        self.close()
