# SPDX-License-Identifier: BSD-3-Clause
"""Exact-plan confirmation on the original authenticated local connection.

The offer is chosen by the trusted planner after native admission. Confirmation
is neither polkit authorization, supply proof, a signed grant nor boot success.
No listener, default admission provider or persistent consent cache lives here.
"""
from __future__ import annotations

import array
from dataclasses import dataclass
from enum import Enum, auto
import fcntl
import hashlib
import os
import select
import socket
import stat
import sys
import time
import unicodedata

MAX_PRESENTATION = 1_048_576
OFFER_SIZE = 160
REPLY_SIZE = 48
SEALS = fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE


class Rejected(ValueError):
    pass


def now_ms() -> int:
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME) // 1_000_000


@dataclass(frozen=True)
class Offer:
    request: bytes
    plan: bytes
    generation: bytes
    presentation: bytes
    deadline: int
    size: int
    boot: bytes

    def wire(self) -> bytes:
        for value, size in ((self.request, 16), (self.plan, 32), (self.generation, 32),
                            (self.presentation, 32), (self.boot, 16)):
            if type(value) is not bytes or len(value) != size or not any(value):
                raise Rejected('consent-offer-identity')
        if (type(self.deadline) is not int or not 0 < self.deadline < 2**63 - 1
                or type(self.size) is not int or not 0 < self.size <= MAX_PRESENTATION):
            raise Rejected('consent-offer-bounds')
        return (b'NIAPLN01' + self.request + self.plan + self.generation + self.presentation
                + self.deadline.to_bytes(8, 'big') + self.size.to_bytes(8, 'big') + self.boot + bytes(8))

    @classmethod
    def decode(cls, wire: bytes) -> Offer:
        if len(wire) != OFFER_SIZE or wire[:8] != b'NIAPLN01' or any(wire[152:]):
            raise Rejected('consent-offer-format')
        result = cls(wire[8:24], wire[24:56], wire[56:88], wire[88:120],
                     int.from_bytes(wire[120:128], 'big'), int.from_bytes(wire[128:136], 'big'), wire[136:152])
        if result.wire() != wire:
            raise Rejected('consent-offer-noncanonical')
        return result


def response(offer: Offer, confirm: bool) -> bytes:
    if type(confirm) is not bool:
        raise Rejected('consent-decision')
    return b'NIACNS01' + hashlib.sha256(offer.wire()).digest() + bytes((int(confirm),)) + bytes(7)


def presentation_text(raw: bytes, *, limit: int = MAX_PRESENTATION) -> str:
    if not 0 < limit <= 64 * 1024 * 1024 or not 0 < len(raw) <= limit:
        raise Rejected('consent-presentation-size')
    text = raw.decode('utf-8', errors='strict')
    # Natural-language joining controls remain available. Escape package names
    # in the planner before rendering; raw terminal/bidi control is never sent.
    if any(unicodedata.category(char).startswith('C') and char not in ('\n', '\t', '\u200c', '\u200d')
           for char in text):
        raise Rejected('consent-presentation-control')
    return text


def read_sealed_text(fd: int, size: int, digest: bytes, *, limit: int = MAX_PRESENTATION) -> str:
    if (type(size) is not int or not 0 < size <= limit <= 64 * 1024 * 1024
            or type(digest) is not bytes or len(digest) != 32 or not any(digest)):
        raise Rejected('sealed-text-context')
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid or info.st_nlink != 0
            or info.st_size != size or fcntl.fcntl(fd, fcntl.F_GET_SEALS) & SEALS != SEALS):
        raise Rejected('consent-presentation-seals')
    raw = bytearray()
    for _ in range(1024):
        if len(raw) == size:
            break
        chunk = os.pread(fd, min(65536, size - len(raw)), len(raw))
        if not chunk:
            raise Rejected('consent-presentation-truncated')
        raw.extend(chunk)
    if len(raw) != size or hashlib.sha256(raw).digest() != digest:
        raise Rejected('consent-presentation-digest')
    return presentation_text(bytes(raw), limit=limit)


def read_presentation(fd: int, offer: Offer) -> str:
    return read_sealed_text(fd, offer.size, offer.presentation)


def receive(peer: socket.socket, limit: int) -> tuple[bytes, tuple[int, int], list[int]]:
    """Receive once, release all installed FDs on any malformed control message."""
    owned: list[int] = []
    try:
        message: tuple[bytes, list[tuple[int, int, bytes]], int, object] = peer.recvmsg(
            limit + 1, socket.CMSG_SPACE(12) + socket.CMSG_SPACE(16 * 4),
            socket.MSG_DONTWAIT | socket.MSG_CMSG_CLOEXEC)
        raw, controls, flags, _ = message
        invalid = bool(flags & ~(socket.MSG_CMSG_CLOEXEC | socket.MSG_EOR)) or not raw or len(raw) > limit
        credentials: list[tuple[int, int]] = []
        for level, kind, data in controls:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                values = array.array('i')
                invalid |= bool(len(data) % values.itemsize)
                values.frombytes(data[:len(data) - len(data) % values.itemsize])
                owned.extend(values)
            elif level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS and len(data) == 12:
                credentials.append((int.from_bytes(data[:4], sys.byteorder, signed=True),
                                    int.from_bytes(data[4:8], sys.byteorder, signed=True)))
            else:
                invalid = True
        if invalid or len(credentials) != 1 or credentials[0][0] <= 0 or credentials[0][1] < 0:
            raise Rejected('consent-message-controls')
        return raw, credentials[0], owned
    except BaseException:
        release(owned)
        raise


def release(descriptors: list[int]) -> None:
    owned, descriptors[:] = descriptors[:], []
    errors: list[OSError] = []
    for fd in owned:
        try:
            os.close(fd)
        except OSError as error:
            errors.append(error)
    if errors:
        raise ExceptionGroup('consent-descriptor-release', errors)


class Phase(Enum):
    NEW = auto()
    OFFERED = auto()
    CONFIRMED = auto()
    FAILED = auto()
    CLOSED = auto()


class PlanConsent:
    """Own duplicates; use only after the launcher's request was authenticated.

    Single owner. send_offer/receive_confirmation never wait. After CONFIRMED,
    any packet, disconnect, peer death, context change or expiry revokes consent.
    Keep the original client and this object for the entire physical lifetime.
    """
    def __init__(self, peer: socket.socket, offer: Offer) -> None:
        self.owner = os.getpid()
        self.phase = Phase.NEW
        self.peer: socket.socket | None = None
        self.pidfd = -1
        self.offer = offer
        self.expected = response(offer, True)
        if os.getuid() or os.geteuid() or not 0 < offer.deadline - now_ms() <= 120_000:
            raise Rejected('consent-root-context')
        with open('/proc/sys/kernel/random/boot_id', encoding='ascii') as source:
            boot = bytes.fromhex(source.read(64).strip().replace('-', ''))
        if boot != offer.boot:
            raise Rejected('consent-boot')
        try:
            self.peer = peer.dup()
            if (peer.family != socket.AF_UNIX or peer.type != socket.SOCK_SEQPACKET
                    or peer.getsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED) != 1):
                raise Rejected('consent-credential-channel')
            cred = peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            self.actor = (int.from_bytes(cred[:4], sys.byteorder, signed=True),
                          int.from_bytes(cred[4:8], sys.byteorder, signed=True))
            self.pidfd = peer.getsockopt(socket.SOL_SOCKET, 77)
            os.set_inheritable(self.pidfd, False)
            self._current()
        except BaseException:
            self.close()
            raise

    def _current(self) -> None:
        if (self.owner != os.getpid() or os.getuid() or os.geteuid() or self.peer is None or self.pidfd < 0
                or self.phase in (Phase.FAILED, Phase.CLOSED) or now_ms() >= self.offer.deadline):
            raise Rejected('consent-owner-or-expiry')
        poll = select.poll()
        poll.register(self.pidfd, select.POLLIN)
        if poll.poll(0):
            raise Rejected('consent-actor-ended')

    def send_offer(self, presentation: bytes) -> None:
        fd = -1
        try:
            self._current()
            if self.phase is not Phase.NEW:
                raise Rejected('consent-offer-reuse')
            self.phase = Phase.OFFERED
            assert self.peer is not None
            poll = select.poll()
            poll.register(self.peer, select.POLLIN)
            if poll.poll(0):
                raise Rejected('consent-unconsumed-request-or-early-reply')
            presentation_text(presentation)
            if len(presentation) != self.offer.size or hashlib.sha256(presentation).digest() != self.offer.presentation:
                raise Rejected('consent-offer-presentation')
            fd = os.memfd_create('niayan-plan', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
            offset = 0
            for _ in range(256):
                if offset == len(presentation):
                    break
                count = os.write(fd, presentation[offset:])
                if count <= 0:
                    raise Rejected('consent-presentation-write')
                offset += count
            if offset != len(presentation):
                raise Rejected('consent-presentation-budget')
            fcntl.fcntl(fd, fcntl.F_ADD_SEALS, SEALS)
            self._current()
            assert self.peer is not None
            wire = self.offer.wire()
            if self.peer.sendmsg([wire], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [fd]))],
                                 socket.MSG_DONTWAIT | socket.MSG_NOSIGNAL) != len(wire):
                raise Rejected('consent-offer-delivery-indeterminate')
        except BaseException:
            self.phase = Phase.FAILED
            raise
        finally:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    self.phase = Phase.FAILED
                    raise

    def receive_confirmation(self) -> bool:
        owned: list[int] = []
        try:
            self._current()
            if self.phase is not Phase.OFFERED:
                raise Rejected('consent-reply-order')
            assert self.peer is not None
            try:
                raw, actor, owned = receive(self.peer, REPLY_SIZE)
            except BlockingIOError:
                return False
            if owned or actor != self.actor or raw != self.expected:
                raise Rejected('consent-declined-or-mismatch')
            self.phase = Phase.CONFIRMED
            self.check(self.offer.plan, self.offer.generation, self.offer.request, self.offer.deadline)
            return True
        except BaseException:
            self.phase = Phase.FAILED
            raise
        finally:
            release(owned)

    def check(self, plan: bytes, generation: bytes, request: bytes, deadline: int) -> None:
        try:
            self._current()
            if (self.phase is not Phase.CONFIRMED or (plan, generation, request, deadline) !=
                    (self.offer.plan, self.offer.generation, self.offer.request, self.offer.deadline)):
                raise Rejected('consent-not-confirmed-for-context')
            assert self.peer is not None
            poll = select.poll()
            poll.register(self.peer, select.POLLIN)
            if poll.poll(0):
                raise Rejected('consent-cancel-or-disconnect')
        except BaseException:
            if self.phase is not Phase.CLOSED:
                self.phase = Phase.FAILED
            raise

    def close(self) -> None:
        self.phase = Phase.CLOSED
        peer, self.peer = self.peer, None
        fd, self.pidfd = self.pidfd, -1
        try:
            if peer is not None:
                peer.close()
        finally:
            if fd >= 0:
                os.close(fd)
