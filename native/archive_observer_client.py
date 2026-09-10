# SPDX-License-Identifier: BSD-3-Clause
"""Internal core client. Receipt authentication is not generation admission."""
import array
import fcntl
import os
import pwd
import socket
import stat
import struct
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from archive_observer import SOCKET, MAX_PACKET, MAX_POLICY, SEALS, request
from archive_receipt import Receipt, DOMAIN, MAGIC
from nia_common import Invalid, canonical, fields, parse_json, sha


def observe(job: dict, originals: list[int], *, public_key: bytes) -> Receipt:
    raw = canonical(job)
    request(raw)
    if len(originals) != 3 or not isinstance(public_key, bytes) or len(public_key) != 32:
        raise Invalid('observer client input')
    fds = []
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC) as connection:
        connection.settimeout(130)
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        connection.connect(SOCKET)
        # systemd owns the listening endpoint; the response also needs the
        # kernel-supplied credentials of the process actually sending it.
        _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != 0:
            raise Invalid('observer listener is not owned by the system manager')
        if connection.sendmsg([raw], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', originals))]) != len(raw):
            raise OSError('short observer request')
        reply, ancillary, flags, _ = connection.recvmsg(MAX_PACKET, socket.CMSG_SPACE(8*4)+socket.CMSG_SPACE(12), socket.MSG_CMSG_CLOEXEC)
        try:
            identities = []
            unexpected = False
            for level, kind, data in ancillary:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    values = array.array('i'); values.frombytes(data); fds.extend(values)
                elif level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS and len(data) == 12:
                    identities.append(struct.unpack('3i', data))
                else:
                    unexpected = True
            server_uid = pwd.getpwnam('nia-supply').pw_uid
            if (unexpected or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) or len(identities) != 1
                    or server_uid == 0 or identities[0][1] != server_uid):
                raise Invalid('observer response sender or packet')
            value = parse_json(reply, limit=MAX_PACKET)
            if (value.get('schema') != 'org.niaos.archive-observer-result/v1'
                    or value.get('request_id') != job['request_id'] or value.get('execution_permit') is not False
                    or value.get('status') != 'authenticated' or canonical(value) != reply or len(fds) != 2):
                raise Invalid('observer rejected the request')
            fields(value, 'schema request_id status receipt_sha256 policy_sha256 execution_permit', 'observer result')
            contents = []
            for fd, maximum in zip(fds, (320, MAX_POLICY)):
                info = os.fstat(fd)
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != server_uid or info.st_nlink != 0
                        or stat.S_IMODE(info.st_mode) != 0o400 or not 1 <= info.st_size <= maximum
                        or fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY
                        or fcntl.fcntl(fd, fcntl.F_GET_SEALS) & SEALS != SEALS):
                    raise Invalid('observer result descriptor protection')
                data = os.pread(fd, maximum+1, 0)
                if len(data) != info.st_size:
                    raise Invalid('observer result descriptor length')
                contents.append(data)
            wire, policy = contents
            if (len(wire) != 320 or wire[:8] != MAGIC or wire[8:40].hex() != job['scope']
                    or sha(wire) != value['receipt_sha256'] or sha(policy) != value['policy_sha256']
                    or wire[40:72].hex() != sha(policy)):
                raise Invalid('observer result binding')
            Ed25519PublicKey.from_public_bytes(public_key).verify(wire[256:], struct.pack('>H', len(DOMAIN))+DOMAIN+wire[:256])
            checked, expires = struct.unpack('>QQ', wire[240:256])
            if not checked <= int(time.time()) < expires:
                raise Invalid('observer result time')
            # Native publication must still bind all original CAS objects,
            # current site epoch/age, plan coverage and its actual reservation.
            return Receipt(wire, policy)
        finally:
            for fd in fds:
                os.close(fd)
