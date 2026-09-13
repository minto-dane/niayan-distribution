# SPDX-License-Identifier: BSD-3-Clause
"""Authenticated request decoding for the root launcher's accepted connection.

No socket activation loop or executor is installed here. Callers must route the
parsed request through native planning/admission before issuing a PlanConsent.
Paths/operands remain untrusted selectors, never root filesystem capabilities.
"""
from dataclasses import dataclass
from enum import IntEnum
import json
import os
import re
import select
import socket
import sys
from typing import cast

from management_grammar import HELP, Request, parse
from plan_consent import Rejected, now_ms, presentation_text, receive, release


@dataclass(frozen=True)
class Command:
    request: Request
    actor_pid: int
    actor_uid: int
    languages: tuple[str, ...]


def string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = cast(list[object], value)
    result: list[str] = []
    for item in items:
        if not isinstance(item, str):
            return None
        result.append(item)
    return result


def read_request(peer: socket.socket, deadline: int) -> Command:
    """One nonblocking receive on a fresh accepted, already PASSCRED socket."""
    descriptors: list[int] = []
    pidfd = -1
    try:
        if (os.getuid() or os.geteuid() or type(deadline) is not int
                or not 0 < deadline - now_ms() <= 600000 or peer.family != socket.AF_UNIX
                or peer.type != socket.SOCK_SEQPACKET or peer.getsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED) != 1):
            raise Rejected('management-receiver-context')
        identity = peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        expected = (int.from_bytes(identity[:4], sys.byteorder, signed=True),
                    int.from_bytes(identity[4:8], sys.byteorder, signed=True))
        pidfd = peer.getsockopt(socket.SOL_SOCKET, 77)
        os.set_inheritable(pidfd, False)
        guard = select.poll()
        guard.register(pidfd, select.POLLIN)
        if guard.poll(0):
            raise Rejected('management-requester-ended')
        raw, actor, descriptors = receive(peer, 65536)
        if descriptors or actor != expected or actor[1] > 2**31 - 1:
            raise Rejected('management-request-sender')
        value = cast(object, json.loads(raw))
        if not isinstance(value, dict):
            raise Rejected('management-request-object')
        fields = cast(dict[object, object], value)
        if set(fields) != {'version', 'command', 'arguments', 'languages'}:
            raise Rejected('management-request-fields')
        if type(fields['version']) is not int or fields['version'] != 1:
            raise Rejected('management-request-version')
        command = fields['command']
        arguments = string_list(fields['arguments'])
        languages = string_list(fields['languages'])
        if (not isinstance(command, str) or command not in HELP or arguments is None
                or len(arguments) > 4096 or any(len(v) > 8192 or '\0' in v for v in arguments)
                or languages is None or not 1 <= len(languages) <= 64
                or any(not re.fullmatch('[a-z][A-Za-z0-9_@-]{0,63}', v) for v in languages)):
            raise Rejected('management-request-values')
        canonical = (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii')
        if canonical != raw:
            raise Rejected('management-request-noncanonical')
        parsed = parse(command, arguments)
        if guard.poll(0) or now_ms() >= deadline:
            raise Rejected('management-request-expired')
        return Command(parsed, actor[0], actor[1], tuple(languages))
    finally:
        try:
            release(descriptors)
        finally:
            if pidfd >= 0:
                os.close(pidfd)


class Disposition(IntEnum):
    COMMITTED = 0
    REFUSED = 1
    INDETERMINATE = 2
    PREVIEW = 3
    READ_ONLY = 4


def send_result(peer: socket.socket, request: bytes, disposition: Disposition, text: str) -> None:
    """Serialize a native terminal result; never infer one from a prepare ACK.

    COMMITTED is reserved for independently reconciled accepted catalog/effects,
    not successful staging. The caller retains the same actor/scope and must not
    report a different request's recorded result on this connection.
    """
    if (os.getuid() or os.geteuid() or type(request) is not bytes or len(request) != 16 or not any(request)
            or not isinstance(disposition, Disposition)):
        raise Rejected('management-result-context')
    raw = text.encode('utf-8')
    presentation_text(raw)
    if len(raw) > 65536 - 32:
        raise Rejected('management-result-size')
    wire = b'NIARSL01' + bytes((disposition,)) + bytes(7) + request + raw
    if peer.send(wire, socket.MSG_DONTWAIT | socket.MSG_NOSIGNAL) != len(wire):
        raise Rejected('management-result-delivery-indeterminate')
