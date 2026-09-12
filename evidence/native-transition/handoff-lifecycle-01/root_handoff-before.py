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
import hashlib
import os
import select
import socket
import struct
import time


class Rejected(ValueError):
    pass


def now_ms() -> int:
    return int(time.clock_gettime(time.CLOCK_BOOTTIME) * 1000)


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


class Channel:
    """Own duplicates and received FDs only; never close/reap/kill the caller's child.

    Caller enables SO_PASSCRED on both socketpair ends before spawning the child.
    PID comes from that launch, never a request field. waitid(P_PIDFD, WNOWAIT)
    requires the still-live, unreaped direct child and prevents PID reuse fallback.
    Only its message UID/PID can transfer FDs; descendants cannot impersonate it.
    Single owning process/task; close does not shut down a parent's forked copy.
    """
    def __init__(self, peer: socket.socket, child_pid: int, child_uid: int, scope: Scope) -> None:
        self.peer = None
        self.pidfd = -1
        self.descriptors = []
        self.received = self.used = self.finished = False
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
        except BaseException:
            self.close()
            raise

    def _alive(self) -> None:
        if self.owner != os.getpid() or os.getuid() or os.geteuid() or now_ms() >= self.scope.deadline:
            raise Rejected('owner-or-deadline')
        if self.pidfd < 0 or os.waitid(os.P_PIDFD, self.pidfd, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None:
            raise Rejected('child-exited')

    def _wait(self, events: int) -> None:
        while True:
            self._alive()
            poll = select.poll()
            poll.register(self.peer.fileno(), events)
            poll.register(self.pidfd, select.POLLIN)
            for fd, flags in poll.poll(min(1000, max(1, self.scope.deadline - now_ms()))):
                if fd == self.pidfd or flags & (select.POLLERR | select.POLLHUP | select.POLLNVAL):
                    raise Rejected('child-or-channel-ended')
                if flags & events:
                    return

    def receive(self) -> tuple[int, int]:
        if self.used:
            raise Rejected('request-already-attempted')
        self.used = True
        try:
            self._wait(select.POLLIN)
            raw, controls, flags, _ = self.peer.recvmsg(
                193, socket.CMSG_SPACE(12) + socket.CMSG_SPACE(16 * 4),
                socket.MSG_DONTWAIT | socket.MSG_CMSG_CLOEXEC)
            credentials, invalid = [], bool(flags & ~(socket.MSG_CMSG_CLOEXEC | socket.MSG_EOR))
            for level, kind, data in controls:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    values = array.array('i')
                    invalid |= bool(len(data) % values.itemsize)
                    values.frombytes(data[:len(data) - len(data) % values.itemsize])
                    self.descriptors.extend(values)
                elif level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS and len(data) == 12:
                    credentials.append(struct.unpack('3i', data))
                else:
                    invalid = True
            if (invalid or len(credentials) != 1 or credentials[0][:2] != (self.child_pid, self.child_uid)
                    or len(self.descriptors) != 2 or raw != self.expected):
                raise Rejected('sender-scope-or-descriptors')
            self._current()
            self.received = True
            return self.descriptors[0], self.descriptors[1]
        except BaseException:
            self._release_inputs()
            raise

    def _current(self) -> None:
        self._alive()
        poll = select.poll()
        poll.register(self.peer.fileno(), select.POLLIN)
        if poll.poll(0):
            raise Rejected('cancel-or-disconnect')

    def complete(self) -> None:
        # Caller has completed its root session request, independent observation
        # and current admission rechecks. No callback is silently supplied here.
        if not self.received or self.finished:
            raise Rejected('not-received-or-finished')
        self.finished = True
        self._release_inputs()
        self._current()
        self._wait(select.POLLOUT)
        reply = b'NIAHOK01' + hashlib.sha256(self.expected).digest()
        if self.peer.send(reply, socket.MSG_DONTWAIT | socket.MSG_NOSIGNAL) != len(reply):
            raise Rejected('uncertain-reply')

    def _release_inputs(self) -> None:
        while self.descriptors:
            os.close(self.descriptors.pop())

    def close(self) -> None:
        self._release_inputs()
        if self.pidfd >= 0:
            os.close(self.pidfd)
            self.pidfd = -1
        if self.peer is not None:
            self.peer.close()
            self.peer = None

    def __enter__(self) -> Channel:
        return self

    def __exit__(self, *ignored: object) -> None:
        self.close()
