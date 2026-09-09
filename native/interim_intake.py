# SPDX-License-Identifier: MIT
"""Authenticate an interim artifact and its exact references in one supply session.

Authentication of contract bytes is deliberately separate from interpreting
them or observing installed state. The same Repository API accepts ordinary
DEBs, source manifests and effect contracts; there is no interim trust database.
"""
from __future__ import annotations

from dataclasses import dataclass
import time

from interim_package import MAX_PACKAGE, decode
from repository import Repository, MAX_METADATA
from nia_common import Invalid, integer, sha


@dataclass(frozen=True)
class AuthenticatedInterim:
    artifact: bytes
    references: tuple[tuple[str, bytes], ...]
    target: str
    security_epoch: int
    checked_at: int

    def observation(self):
        return {'schema': 'org.niaos.interim-supply-observation/v1',
                'target': self.target, 'artifact_sha256': sha(self.artifact),
                'repository_authenticated': True, 'references_authenticated': True,
                'security_epoch': self.security_epoch, 'checked_at': self.checked_at,
                'references': [{'target': path, 'sha256': sha(raw)} for path, raw in self.references],
                'contract_semantics_checked': False, 'debian_archive_authenticated': False,
                'current_base_checked': False, 'execution_permit': False}


def authenticate(repository: Repository, target: str, *, minimum_security_epoch: int) -> AuthenticatedInterim:
    integer(minimum_security_epoch, 1, 2**53 - 1, 'independent security epoch floor')
    raw = repository.target(target, MAX_PACKAGE)
    manifest, _ = decode(raw)
    now = int(time.time())
    if not manifest['created_at'] <= now < manifest['expires_at']:
        raise Invalid('interim artifact is expired or not yet valid')
    if manifest['security_epoch'] < minimum_security_epoch:
        raise Invalid('interim security epoch below trusted floor')
    objects = {'contracts/rollback/' + manifest['rollback_contract_sha256'] + '.json':
               manifest['rollback_contract_sha256']}
    for replacement in manifest['replacements']:
        effect = replacement['effect_contract_sha256']
        objects['contracts/effects/' + effect + '.json'] = effect
        for side in ('base', 'target'):
            source = replacement[side]['source_manifest_sha256']
            objects['sources/' + source + '.json'] = source
    references = []
    for path, expected in sorted(objects.items()):
        data = repository.target(path, MAX_METADATA)
        if sha(data) != expected:
            raise Invalid('authenticated reference differs from interim manifest')
        references.append((path, data))
    # Each reference is verified by TUF, including its delegated publishing role.
    # A valid signature on only the outer package cannot supply missing contracts.
    now = int(time.time())
    if not manifest['created_at'] <= now < manifest['expires_at']:
        raise Invalid('interim artifact expired during intake')
    return AuthenticatedInterim(raw, tuple(references), target, manifest['security_epoch'], now)
