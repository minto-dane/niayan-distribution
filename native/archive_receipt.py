# SPDX-License-Identifier: MIT
"""Issue a native original-supply receipt after both existing authenticators.

The caller supplies a protected, scoped signing provider and its independent
public-key pin. No key generation, key storage, default authority or public CLI.
Only this observer's result is signed; caller-constructed observations are not
accepted as inputs. A receipt authenticates supply, never generation execution.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import struct
import time
from typing import Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from archive_intake import authenticate
from nia_common import Invalid, canonical, integer, sha
from repository import Repository, MAX_SESSION_SECONDS, target_path

DOMAIN = b'NiaOS/archive-supply/v1'
MAGIC = b'NIASUP01'
BODY_SIZE = 256
WIRE_SIZE = 320
MAX_LIFETIME = 3600


@dataclass(frozen=True)
class Receipt:
    wire: bytes
    policy_bytes: bytes


def scope(repository: Repository, target: str) -> str:
    """Public derivation; the native expected value must come from site policy."""
    target_path(target)
    return sha(canonical({'schema': 'org.niaos.archive-scope/v1',
                          'repository': repository.identity, 'target': target}))


def issue(repository: Repository, target: str, snapshot: Path, keyring: bytes,
          index: str, deb: str, *, minimum_security_epoch: int,
          maximum_lifetime_seconds: int, public_key: bytes,
          sign: Callable[[bytes], bytes]) -> Receipt:
    if os.geteuid() == 0:
        raise Invalid('unprivileged archive receipt issuer required')
    integer(maximum_lifetime_seconds, 1, MAX_LIFETIME, 'archive receipt lifetime')
    if not isinstance(public_key, bytes) or len(public_key) != 32 or public_key == bytes(32):
        raise Invalid('independent archive observer public key required')
    if not callable(sign):
        raise Invalid('archive observer signing provider required')
    started = time.monotonic()
    result = authenticate(repository, target, snapshot, keyring, index, deb,
                          minimum_security_epoch=minimum_security_epoch)
    expires = min(result.valid_until, result.checked_at+maximum_lifetime_seconds)
    hashes = (scope(repository, target), sha(result.policy_bytes), result.original,
              result.control, result.inrelease, result.index, sha(keyring))
    body = MAGIC+b''.join(bytes.fromhex(value) for value in hashes)
    body += struct.pack('>QQQ', result.security_epoch, result.checked_at, expires)
    message = struct.pack('>H', len(DOMAIN))+DOMAIN+body
    signature = sign(message)
    if not isinstance(signature, bytes) or len(signature) != 64:
        raise Invalid('archive observer signature size/type')
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
    except InvalidSignature as exc:
        raise Invalid('archive observer signature differs from independent key') from exc
    # A remote/HSM provider can take time. Never publish after retained policy,
    # metadata, reservation or the finite issuance deadline ceased to hold.
    valid_until = repository.revalidate_target(target, result.policy_bytes)
    now = int(time.time())
    if (not result.checked_at <= now < min(expires, valid_until)
            or time.monotonic()-started >= MAX_SESSION_SECONDS):
        raise Invalid('archive receipt expired or clock moved backward during signing')
    return Receipt(body+signature, result.policy_bytes)
