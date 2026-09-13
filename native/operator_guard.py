# SPDX-License-Identifier: BSD-3-Clause
"""Asynchronous private native operator checks owned by a root supervisor.

The accepted request and exact-plan consent must already be authenticated and
consumed. This observation grants no supply, generation or physical authority.
Caller polls descriptors and next_deadline while supervising effects, requests
fresh checks at effect boundaries, and closes this object on every exit path.
"""
from dataclasses import dataclass
from enum import Enum, auto
import os
import select
import signal
import socket
import struct
import subprocess
import time

import native_helper

HELPER = '/usr/libexec/nia/pkg_operator_guard'
MAX_CHECKS = 1200
CHECK_MS = 1000


class Rejected(ValueError):
    pass


class Phase(Enum):
    NEW = auto()
    PENDING = auto()
    OBSERVED = auto()
    FAILED = auto()
    CLOSED = auto()


def advance(phase: Phase, event: str, sequence: int) -> tuple[Phase, int]:
    if event == 'close':
        return Phase.CLOSED, sequence
    if event == 'fail' and phase not in (Phase.FAILED, Phase.CLOSED):
        return Phase.FAILED, sequence
    if event == 'request' and phase in (Phase.NEW, Phase.OBSERVED) and 0 <= sequence < MAX_CHECKS:
        return Phase.PENDING, sequence + 1
    if event == 'observe' and phase is Phase.PENDING and 1 <= sequence <= MAX_CHECKS:
        return Phase.OBSERVED, sequence
    raise Rejected('operator-check-order')


def now_ms() -> int:
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME) // 1_000_000


def executable() -> int:
    try:
        return native_helper.executable('pkg_operator_guard')
    except native_helper.Rejected as error:
        raise Rejected(str(error)) from error


@dataclass(frozen=True)
class Observation:
    sequence: int
    started: int
    finished: int


class OperatorGuard:
    """Single owning process, no external reaper; observations are not tickets.

    NEW/PENDING cannot be used as authorization. A returned Observation is a
    point-in-time native check only, never a cached permit for later effects.
    Native refusal, helper death/stall and peer cancellation poison the object.
    close releases this observer; it does not revoke already-started effects or
    prove the controller's cleanup. The supervisor must stop those separately.
    """
    def __init__(self, peer: socket.socket, plan: bytes, request: bytes,
                 deadline: int, *, interactive: bool) -> None:
        self.owner = os.getpid()
        self.phase, self.sequence = Phase.NEW, 0
        self.peer: socket.socket | None = None
        self.peer_pidfd = self.pidfd = -1
        self.child: subprocess.Popen[bytes] | None = None
        self.original_deadline = deadline
        self.plan, self.request = plan, request
        self.sent_at = self.next_deadline = 0
        self.buffer = bytearray()
        if (os.getuid() or os.geteuid() or type(interactive) is not bool
                or type(deadline) is not int or not 0 < deadline - now_ms() <= 120_000
                or deadline > 2**63 - 1 or type(plan) is not bytes or len(plan) != 32 or not any(plan)
                or type(request) is not bytes or len(request) != 16 or not any(request)):
            raise Rejected('operator-context')
        try:
            self.peer = peer.dup()
            if self.peer.family != socket.AF_UNIX or self.peer.type != socket.SOCK_SEQPACKET:
                raise Rejected('accepted-seqpacket-required')
            self.peer_pidfd = self.peer.getsockopt(socket.SOL_SOCKET, 77)  # SO_PEERPIDFD, no PID fallback
            os.set_inheritable(self.peer_pidfd, False)
            pinned = executable()
            try:
                self.child = subprocess.Popen([HELPER, str(self.peer.fileno()), plan.hex(), request.hex(),
                    str(deadline), '--interactive' if interactive else '--noninteractive'],
                    executable=f'/proc/self/fd/{pinned}', pass_fds=(pinned, self.peer.fileno()),
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    start_new_session=True, bufsize=0, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'})
            finally:
                os.close(pinned)
            self.pidfd = os.pidfd_open(self.child.pid)
            os.set_inheritable(self.pidfd, False)
            if self.child.stdin is None or self.child.stdout is None:
                raise Rejected('operator-pipes')
            os.set_blocking(self.child.stdin.fileno(), False)
            os.set_blocking(self.child.stdout.fileno(), False)
            self._current()
        except BaseException:
            self.close()
            raise

    def _step(self, event: str) -> None:
        self.phase, self.sequence = advance(self.phase, event, self.sequence)

    def _current(self) -> int:
        current = now_ms()
        if (self.owner != os.getpid() or os.getuid() or os.geteuid()
                or self.phase in (Phase.FAILED, Phase.CLOSED) or current >= self.original_deadline
                or self.child is None or self.peer is None or min(self.pidfd, self.peer_pidfd) < 0):
            raise Rejected('operator-owner-or-deadline')
        check = select.poll()
        for fd in (self.peer.fileno(), self.peer_pidfd, self.pidfd):
            check.register(fd, select.POLLIN)
        if check.poll(0):
            raise Rejected('operator-peer-cancelled-or-helper-ended')
        if self.phase is Phase.PENDING and current >= self.next_deadline:
            raise Rejected('operator-observation-timeout')
        return current

    def descriptors(self) -> tuple[int, int, int, int]:
        try:
            self._current()
            assert self.child is not None and self.child.stdout is not None and self.peer is not None
            return self.child.stdout.fileno(), self.pidfd, self.peer.fileno(), self.peer_pidfd
        except BaseException:
            if self.phase not in (Phase.FAILED, Phase.CLOSED):
                self._step('fail')
            raise

    def request_check(self) -> None:
        try:
            self.sent_at = self._current()
            self._step('request')
            self.next_deadline = min(self.original_deadline,
                self.sent_at + (120_000 if self.sequence == 1 else CHECK_MS))
            self.buffer.clear()
            assert self.child is not None and self.child.stdin is not None
            if os.write(self.child.stdin.fileno(), struct.pack('>Q', self.sequence)) != 8:
                raise Rejected('operator-request-write')
        except BaseException:
            if self.phase not in (Phase.FAILED, Phase.CLOSED):
                self._step('fail')
            raise

    def receive(self) -> Observation | None:
        try:
            self._current()
            if self.phase is not Phase.PENDING:
                raise Rejected('operator-no-pending-check')
            assert self.child is not None and self.child.stdout is not None
            try:
                data = os.read(self.child.stdout.fileno(), 33 - len(self.buffer))
            except BlockingIOError:
                return None
            if not data:
                raise Rejected('operator-refused-or-ended')
            self.buffer.extend(data)
            if len(self.buffer) < 32:
                return None
            if len(self.buffer) != 32 or self.buffer[:8] != b'NIAOPR01':
                raise Rejected('operator-observation-format')
            sequence, started, finished = (int.from_bytes(self.buffer[offset:offset+8], 'big')
                                           for offset in (8, 16, 24))
            current = self._current()
            if (sequence != self.sequence or not self.sent_at <= started <= finished <= current
                    or current - finished > CHECK_MS):
                raise Rejected('operator-observation-context')
            self._step('observe')
            self.buffer.clear()
            return Observation(sequence, started, finished)
        except BaseException:
            if self.phase not in (Phase.FAILED, Phase.CLOSED):
                self._step('fail')
            raise

    def close(self) -> None:
        self._step('close')
        self.buffer.clear()
        failures: list[BaseException] = []
        child, self.child = self.child, None
        if child is not None and self.owner == os.getpid():
            try:
                # Keep the direct leader unreaped across killpg, even if exited.
                os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=5)
            except BaseException as error:
                failures.append(error)
        if child is not None:
            for stream in (child.stdin, child.stdout):
                if stream is not None:
                    try:
                        stream.close()
                    except BaseException as error:
                        failures.append(error)
        descriptors = (self.pidfd, self.peer_pidfd)
        self.pidfd = self.peer_pidfd = -1
        for fd in descriptors:
            if fd >= 0:
                try:
                    os.close(fd)
                except BaseException as error:
                    failures.append(error)
        peer, self.peer = self.peer, None
        if peer is not None:
            try:
                peer.close()
            except BaseException as error:
                failures.append(error)
        if failures:
            raise BaseExceptionGroup('operator-observer-close-indeterminate', failures)
