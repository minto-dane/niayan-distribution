# SPDX-License-Identifier: BSD-3-Clause
"""One bounded sealed read-only result; never a plan offer or commit receipt."""
import array
import fcntl
import hashlib
import os
import socket

from plan_consent import Rejected, SEALS, presentation_text, read_sealed_text

MAGIC = b'NIAQRSL1'
LIMIT = 64 * 1024 * 1024


def read(wire: bytes, fd: int) -> str:
    if (len(wire) != 96 or wire[:8] != MAGIC or not any(wire[8:24])
            or not any(wire[24:56]) or not any(wire[56:88])):
        raise Rejected('management-query-result-format')
    return read_sealed_text(fd, int.from_bytes(wire[88:96], 'big'), wire[56:88], limit=LIMIT)


def send(peer: socket.socket, request: bytes, descriptor: bytes, text: str) -> None:
    if (os.getuid() or os.geteuid() or type(request) is not bytes or len(request) != 16
            or not any(request) or type(descriptor) is not bytes or len(descriptor) != 192):
        raise Rejected('management-query-result-context')
    raw = text.encode('utf-8')
    presentation_text(raw, limit=LIMIT)
    wire = MAGIC + request + hashlib.sha256(descriptor).digest() + hashlib.sha256(raw).digest() + len(raw).to_bytes(8, 'big')
    fd = os.memfd_create('niayan-query-result', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        offset = 0
        for _ in range(2048):
            if offset == len(raw):
                break
            written = os.write(fd, raw[offset:offset + 65536])
            if written <= 0:
                raise Rejected('management-query-result-write')
            offset += written
        if offset != len(raw):
            raise Rejected('management-query-result-write-budget')
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, SEALS)
        if peer.sendmsg([wire], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [fd]))],
                        socket.MSG_DONTWAIT | socket.MSG_NOSIGNAL) != len(wire):
            raise Rejected('management-query-result-delivery-indeterminate')
    finally:
        os.close(fd)
