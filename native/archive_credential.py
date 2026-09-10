# SPDX-License-Identifier: BSD-3-Clause
"""Credential-backed archive observation; never a raw-message signing service.

The supervisor supplies a read-only, immutable credential FD and independent
site pins. Use a separate short-lived unprivileged observer process: disabling
core dumps and dumpability is intentional and is not reversed on return.
"""
from __future__ import annotations

import ctypes
import fcntl
import hmac
import os
from pathlib import Path
import resource
import stat
import struct

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from archive_receipt import (BODY_SIZE, DOMAIN, MAGIC, MAX_LIFETIME, Receipt,
                             issue, scope)
from nia_common import Invalid, digest, integer
from repository import Repository

_SEALS = fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE
_PREFIX = struct.pack('>H', len(DOMAIN)) + DOMAIN


def _protect_process() -> None:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.restype = ctypes.c_int
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                          ctypes.c_ulong, ctypes.c_ulong]
    # Linux PR_SET_DUMPABLE / PR_GET_DUMPABLE. No secret has been read yet.
    if libc.prctl(4, 0, 0, 0, 0) != 0 or libc.prctl(3, 0, 0, 0, 0) != 0:
        raise Invalid('archive observer process protection unavailable')


def _metadata(fd: int) -> tuple:
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_size != 32
            or fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY):
        raise Invalid('private read-only 32-byte archive credential required')
    acl = b''
    if info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o400:
        pass
    elif info.st_uid == 0 and info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 0o440:
        # systemd 257 keeps root ownership and grants exactly the service UID
        # read access through a POSIX ACL. The displayed group bits are its
        # mask, not group access. Reject additional users/groups or permissions.
        undefined = 2**32-1
        expected_acl = struct.pack('<I', 2) + b''.join(struct.pack('<HHI', *entry) for entry in (
            (1, 4, undefined), (2, 4, os.geteuid()), (4, 0, undefined),
            (16, 4, undefined), (32, 0, undefined)))
        try:
            acl = os.getxattr(fd, 'system.posix_acl_access')
        except OSError:
            raise Invalid('archive credential requires the exact service ACL') from None
        if acl != expected_acl:
            raise Invalid('archive credential requires the exact service ACL')
    else:
        raise Invalid('private read-only 32-byte archive credential required')
    # systemd credentials live on a read-only mount. A sealed memfd is also
    # supported for a supervisor that transfers credentials directly by FD.
    # A read-only descriptor on an ordinary writable filesystem is insufficient.
    readonly = bool(os.fstatvfs(fd).f_flag & os.ST_RDONLY)
    if readonly:
        if info.st_nlink != 1:
            raise Invalid('archive credential link count')
    else:
        try:
            seals = fcntl.fcntl(fd, fcntl.F_GET_SEALS)
        except OSError:
            raise Invalid('archive credential storage is mutable') from None
        if info.st_nlink != 0 or seals & _SEALS != _SEALS:
            raise Invalid('archive credential storage is mutable')
    return (info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns, readonly, acl)


def issue_from_credential(repository: Repository, target: str, snapshot: Path,
                          keyring: bytes, index: str, deb: str, *, credential_fd: int,
                          expected_scope: str, public_key: bytes,
                          minimum_security_epoch: int,
                          maximum_lifetime_seconds: int) -> Receipt:
    """Authenticate originals, then use exactly one pinned credential signature.

    This API accepts archive inputs, not observations or arbitrary messages.
    The FD is borrowed: a private CLOEXEC duplicate is closed on every exit and
    pread leaves the caller's offset untouched. Pins must be provisioned by the
    supervisor independently of the request, receipt and credential itself.
    """
    if os.geteuid() == 0:
        raise Invalid('unprivileged archive credential observer required')
    integer(credential_fd, 0, 2**31-1, 'archive credential descriptor')
    digest(expected_scope)
    integer(minimum_security_epoch, 1, 2**53-1, 'independent security epoch floor')
    integer(maximum_lifetime_seconds, 1, MAX_LIFETIME, 'archive receipt lifetime')
    if not isinstance(public_key, bytes) or len(public_key) != 32 or public_key == bytes(32):
        raise Invalid('independent archive observer public key required')
    if scope(repository, target) != expected_scope:
        raise Invalid('archive observer scope differs from site pin')
    _protect_process()
    fd = fcntl.fcntl(credential_fd, fcntl.F_DUPFD_CLOEXEC, 3)
    try:
        before = _metadata(fd)
        used = False

        def sign_authenticated(message: bytes) -> bytes:
            nonlocal used
            if used:
                raise Invalid('archive credential invocation already consumed')
            used = True
            if (not isinstance(message, bytes) or len(message) != len(_PREFIX)+BODY_SIZE
                    or not message.startswith(_PREFIX+MAGIC)):
                raise Invalid('archive credential signing domain')
            body = message[len(_PREFIX):]
            epoch, checked, expires = struct.unpack('>QQQ', body[232:256])
            if (body[8:40].hex() != expected_scope
                    or not minimum_security_epoch <= epoch <= 2**53-1
                    or not 1 <= checked < expires <= 2**53-1
                    or expires-checked > maximum_lifetime_seconds):
                raise Invalid('archive credential signing scope or limits')
            if _metadata(fd) != before:
                raise Invalid('archive credential changed before signing')
            # issue() reaches here only after real TUF/OpenPGP authentication.
            seed = os.pread(fd, 33, 0)
            if len(seed) != 32 or _metadata(fd) != before:
                raise Invalid('archive credential changed while reading')
            key = Ed25519PrivateKey.from_private_bytes(seed)
            try:
                actual = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
                if not hmac.compare_digest(actual, public_key):
                    raise Invalid('archive credential differs from independent key')
                signature = key.sign(message)
                if _metadata(fd) != before:
                    raise Invalid('archive credential changed during signing')
                return signature
            finally:
                # Python/OpenSSL do not promise erasure of every copied byte.
                # Drop references; process exit and supervisor isolation remain
                # required. Never log the credential or include it in errors.
                del key, seed

        return issue(repository, target, snapshot, keyring, index, deb,
                     minimum_security_epoch=minimum_security_epoch,
                     maximum_lifetime_seconds=maximum_lifetime_seconds,
                     public_key=public_key, sign=sign_authenticated)
    finally:
        os.close(fd)
