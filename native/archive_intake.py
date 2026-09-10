# SPDX-License-Identifier: MIT
"""Join shared TUF policy authentication to the original Debian archive chain.

No installed database, writer, signing key, admission certificate or public CLI.
The caller owns the Repository session and supplies its independent epoch floor.
Returned hashes must be matched to native CAS originals; a serialized observation
is never a grant to execute a generation plan.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import time

from repository import Repository, MAX_METADATA
from nia_common import Invalid, fields, integer, parse_json, sha
from debian_archive_auth import auth_policy, verify_snapshot


@dataclass(frozen=True)
class AuthenticatedArchive:
    policy_bytes: bytes
    target: str
    security_epoch: int
    checked_at: int
    valid_until: int
    codename: str
    architecture: str
    inrelease: str
    index: str
    original: str
    control: str

    def observation(self):
        return {'schema': 'org.niaos.archive-supply-observation/v1',
                'target': self.target, 'policy_sha256': sha(self.policy_bytes),
                'repository_authenticated': True, 'debian_archive_authenticated': True,
                'security_epoch': self.security_epoch, 'checked_at': self.checked_at,
                'valid_until': self.valid_until, 'codename': self.codename,
                'architecture': self.architecture, 'inrelease_sha256': self.inrelease,
                'index_sha256': self.index, 'original_sha256': self.original,
                'raw_control_sha256': self.control, 'execution_permit': False,
                'current_base_checked': False, 'contract_semantics_checked': False,
                'native_cas_bound': False}


def authenticate(repository: Repository, target: str, snapshot: Path, keyring: bytes,
                 index: str, deb: str, *, minimum_security_epoch: int) -> AuthenticatedArchive:
    if os.geteuid() == 0:
        raise Invalid('unprivileged archive intake required')
    integer(minimum_security_epoch, 1, 2**53 - 1, 'independent security epoch floor')
    started = time.monotonic()
    raw = repository.target(target, MAX_METADATA)
    envelope = parse_json(raw)
    fields(envelope, {'schema', 'security_epoch', 'created_at', 'trust'}, 'archive supply policy')
    if envelope['schema'] != 'org.niaos.archive-supply/v1':
        raise Invalid('archive supply policy version')
    integer(envelope['security_epoch'], minimum_security_epoch, 2**53 - 1, 'archive security epoch')
    integer(envelope['created_at'], 1, 2**53 - 1, 'archive policy creation time')
    trust = envelope['trust']
    auth_policy(trust)
    if trust['schema'] != 'org.niaos.debian-trust/v2':
        raise Invalid('pinned version 2 archive policy required')
    before = int(time.time())
    if not envelope['created_at'] <= before < trust['release']['expires']:
        raise Invalid('archive policy not currently valid')
    verified = verify_snapshot(snapshot, keyring, trust, index, deb, now=before)
    after = int(time.time())
    if after < before or after >= verified['valid_until'] or time.monotonic() - started >= 120:
        raise Invalid('archive intake time changed or deadline expired')
    # Fresh upstream verification of our exact retained checkpoint also bounds
    # the observation by every TUF role used to authenticate this target. It
    # preserves the single cache reservation and never contacts a second source.
    valid_until = min(verified['valid_until'], repository.revalidate_target(target, raw))
    checked = int(time.time())
    if checked < after or checked >= valid_until or time.monotonic() - started >= 120:
        raise Invalid('archive policy expired during final recheck')
    observed = verified['observation']
    return AuthenticatedArchive(raw, target, envelope['security_epoch'], checked, valid_until,
                                verified['codename'], trust['release']['architecture'],
                                verified['inrelease_sha256'], verified['index_sha256'],
                                observed['artifact_sha256'], observed['raw_control_sha256'])
