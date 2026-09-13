# SPDX-License-Identifier: BSD-3-Clause
"""Continuous independent supply observations during a held root operation.

A trusted native planner supplies Binding from its admitted transaction and
fresh Pkg_Site_Supply.Observe_Inputs result. No values come from a CLI request.
The managed publisher still authenticates the map, receipts and reservations.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
import hashlib
import os
import pwd
import select
import signal
import struct
import subprocess

import native_helper
from root_handoff import Rejected, now_ms

HELPER = '/usr/libexec/nia/pkg_supply_guard'
CHECK_MS = 1000
MAX_CHECKS = 1200


class Phase(Enum):
    NEW = auto()
    PENDING = auto()
    OBSERVED = auto()
    FAILED = auto()
    CLOSED = auto()


@dataclass(frozen=True)
class Binding:
    generation: bytes
    root: bytes
    transaction: bytes
    plan: bytes
    retained_policy: bytes
    supply_map: bytes
    policy_hash: bytes
    floor_hash: bytes
    minimum_utc: int
    deadline: int

    def arguments(self) -> tuple[str, ...]:
        values = (self.generation, self.root, self.transaction, self.plan,
                  self.retained_policy, self.supply_map, self.policy_hash, self.floor_hash)
        for index, value in enumerate(values):
            if type(value) is not bytes or len(value) != (16 if index in (1, 2) else 32) or not any(value):
                raise Rejected('supply-binding-identity')
        if (type(self.minimum_utc) is not int or not 0 < self.minimum_utc <= 2**53 - 1
                or type(self.deadline) is not int or not 0 < self.deadline < 2**63 - 1):
            raise Rejected('supply-binding-clock')
        return tuple(value.hex() for value in values) + (str(self.minimum_utc), str(self.deadline))

    def digest(self) -> bytes:
        self.arguments()
        return hashlib.sha256(b'NIASUPB1' + self.generation + self.root + self.transaction
            + self.plan + self.retained_policy + self.supply_map + self.policy_hash + self.floor_hash
            + struct.pack('>QQ', self.minimum_utc, self.deadline)).digest()


@dataclass(frozen=True)
class Observation:
    sequence: int
    started: int
    finished: int
    observed_utc: int


class SupplyGuard:
    """Own one unreaped native child and the original deadline, with no retry.

    NEW/PENDING are not positive observations. The supervisor must poll this
    object together with the controller and operator, and stop effects before
    closing observers. The dedicated nonroot account is not the package worker
    or archive signing account; no package/store/secret FDs are inherited.
    """
    def __init__(self, binding: Binding) -> None:
        self.owner = os.getpid()
        self.binding = binding
        self.phase, self.sequence = Phase.NEW, 0
        self.child: subprocess.Popen[bytes] | None = None
        self.pidfd = -1
        self.sent_at = self.next_deadline = 0
        self.last_utc = 0
        self.buffer = bytearray()
        if (os.getuid() or os.geteuid() or type(binding) is not Binding
                or not 0 < binding.deadline - now_ms() <= 120_000):
            raise Rejected('supply-observer-context')
        arguments = binding.arguments()
        self.last_utc = binding.minimum_utc
        self.expected = binding.digest()
        account = pwd.getpwnam('nia-trust')
        if account.pw_uid <= 0 or account.pw_gid <= 0:
            raise Rejected('nonroot-supply-observer-account-required')
        # Reject accidental account aliases to identities handling packages or
        # archive signing keys. Identity setup happens before retaining effects.
        for name in ('nia-pkg', 'nia-supply'):
            try:
                other = pwd.getpwnam(name)
            except KeyError:
                continue
            if account.pw_uid == other.pw_uid or account.pw_gid == other.pw_gid:
                raise Rejected('separate-supply-observer-account-required')
        try:
            pinned = native_helper.executable('pkg_supply_guard')
            try:
                self.child = subprocess.Popen([HELPER, *arguments],
                    executable=f'/proc/self/fd/{pinned}', pass_fds=(pinned,),
                    user=account.pw_uid, group=account.pw_gid, extra_groups=[],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    cwd='/', start_new_session=True, bufsize=0, umask=0o077,
                    env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'})
            finally:
                os.close(pinned)
            self.pidfd = os.pidfd_open(self.child.pid)
            os.set_inheritable(self.pidfd, False)
            if self.child.stdin is None or self.child.stdout is None:
                raise Rejected('supply-observer-pipes')
            os.set_blocking(self.child.stdin.fileno(), False)
            os.set_blocking(self.child.stdout.fileno(), False)
            self._current()
        except BaseException:
            self.close()
            raise

    def _fail(self) -> None:
        if self.phase is not Phase.CLOSED:
            self.phase = Phase.FAILED

    def _current(self) -> int:
        current = now_ms()
        if (self.owner != os.getpid() or os.getuid() or os.geteuid()
                or self.phase in (Phase.FAILED, Phase.CLOSED) or current >= self.binding.deadline
                or self.child is None or self.child.stdout is None or self.pidfd < 0):
            raise Rejected('supply-observer-owner-or-ended')
        poll = select.poll()
        poll.register(self.pidfd, select.POLLIN)
        if self.phase is not Phase.PENDING:
            poll.register(self.child.stdout.fileno(), select.POLLIN)
        if poll.poll(0):
            raise Rejected('supply-observer-ended-or-unsolicited-data')
        if self.phase is Phase.PENDING and current >= self.next_deadline:
            raise Rejected('supply-observation-timeout')
        return current

    def descriptors(self) -> tuple[int, int]:
        try:
            self._current()
            assert self.child is not None and self.child.stdout is not None
            return self.child.stdout.fileno(), self.pidfd
        except BaseException:
            self._fail()
            raise

    def request_check(self) -> None:
        try:
            self.sent_at = self._current()
            if self.phase not in (Phase.NEW, Phase.OBSERVED) or self.sequence >= MAX_CHECKS:
                raise Rejected('supply-observation-order')
            self.sequence += 1
            self.phase = Phase.PENDING
            self.next_deadline = min(self.binding.deadline, self.sent_at + CHECK_MS)
            self.buffer.clear()
            assert self.child is not None and self.child.stdin is not None
            if os.write(self.child.stdin.fileno(), struct.pack('>Q', self.sequence)) != 8:
                raise Rejected('supply-observation-request-write')
        except BaseException:
            self._fail()
            raise

    def receive(self) -> Observation | None:
        try:
            self._current()
            if self.phase is not Phase.PENDING:
                raise Rejected('supply-no-pending-observation')
            assert self.child is not None and self.child.stdout is not None
            try:
                data = os.read(self.child.stdout.fileno(), 73 - len(self.buffer))
            except BlockingIOError:
                return None
            if not data:
                raise Rejected('supply-observation-refused-or-ended')
            self.buffer.extend(data)
            if len(self.buffer) < 72:
                return None
            if (len(self.buffer) != 72 or self.buffer[:8] != b'NIASUP01'
                    or self.buffer[32:64] != self.expected):
                raise Rejected('supply-observation-format-or-binding')
            sequence, started, finished = struct.unpack('>QQQ', self.buffer[8:32])
            observed_utc = int.from_bytes(self.buffer[64:72], 'big')
            current = self._current()
            if (sequence != self.sequence or not self.sent_at <= started <= finished <= current
                    or current - finished > CHECK_MS or not self.last_utc <= observed_utc <= 2**53 - 1):
                raise Rejected('supply-observation-clock-or-sequence')
            self.phase = Phase.OBSERVED
            self.last_utc = observed_utc
            self.buffer.clear()
            self._current()
            return Observation(sequence, started, finished, observed_utc)
        except BaseException:
            self._fail()
            raise

    def close(self) -> None:
        self.phase = Phase.CLOSED
        self.buffer.clear()
        failures: list[BaseException] = []
        child, self.child = self.child, None
        if child is not None and self.owner == os.getpid():
            try:
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
        descriptor, self.pidfd = self.pidfd, -1
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except BaseException as error:
                failures.append(error)
        if failures:
            raise BaseExceptionGroup('supply-observer-close-indeterminate', failures)
