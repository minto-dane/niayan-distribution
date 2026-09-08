#!/usr/bin/python3 -I
# SPDX-License-Identifier: MIT
"""Deterministic, bounded construction and inspection of native interim packages.

This is an unprivileged artifact codec, not an installed-package database or
execution authority. DEBs stay byte-for-byte intact; no extraction or hooks.
Publisher authentication, current-base observation, holds and effect execution
belong to the shared native intake/transaction service, not this module.
"""
from __future__ import annotations

from pathlib import Path
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from deb_archive import inspect_bytes
from debian_semantics import NAME, split_version
from nia_common import Invalid, canonical, digest, fields, integer, parse_json, read_file, sha, write_new

MAGIC = b'NIA-INTERIM\x00\x01'
MAX_MANIFEST = 256 * 1024
MAX_ARTIFACT = 128 * 1024 * 1024
MAX_PAYLOAD = 256 * 1024 * 1024
MAX_REPLACEMENTS = 64
MAX_PACKAGE = len(MAGIC) + 4 + MAX_MANIFEST + MAX_PAYLOAD + MAX_REPLACEMENTS * 2 * 40
LABEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.+-]{0,99}\Z')
IDENTIFIERS = re.compile(r'(?:CVE-[0-9]{4}-[0-9]{4,}|DSA-[0-9]+-[0-9]+|NIA-[A-Za-z0-9_.-]+)\Z')
MANIFEST_FIELDS = {'schema', 'label', 'description', 'release', 'architecture',
                   'created_at', 'expires_at', 'security_epoch', 'advisories',
                   'requires', 'conflicts', 'supersedes', 'rollback_contract_sha256', 'replacements'}
IMAGE_FIELDS = {'package', 'version', 'architecture', 'artifact_sha256', 'source_manifest_sha256'}


def _text(value, limit, name):
    if not isinstance(value, str) or not 1 <= len(value) <= limit:
        raise Invalid(name + ' size/type')
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise Invalid(name + ' control character')
    try:
        value.encode('utf-8')
    except UnicodeError as exc:
        raise Invalid(name + ' invalid Unicode') from exc


def _digests(items, name):
    if not isinstance(items, list) or len(items) > 64:
        raise Invalid(name + ' count/type')
    for item in items:
        digest(item)
    if items != sorted(set(items)):
        raise Invalid(name + ' must be sorted and unique')


def check_manifest(manifest: dict) -> list[str]:
    fields(manifest, MANIFEST_FIELDS, 'interim manifest')
    if manifest['schema'] != 'org.niaos.interim-package/v1':
        raise Invalid('unsupported interim manifest version')
    if not isinstance(manifest['label'], str) or not LABEL.fullmatch(manifest['label']):
        raise Invalid('invalid interim label')
    _text(manifest['description'], 1024, 'description')
    if manifest['release'] != 'trixie' or manifest['architecture'] != 'amd64':
        raise Invalid('unsupported interim platform')
    integer(manifest['created_at'], 1, 2**53 - 2, 'creation time')
    integer(manifest['expires_at'], manifest['created_at'] + 1, 2**53 - 1, 'expiry time')
    integer(manifest['security_epoch'], 1, 2**53 - 1, 'security epoch')
    digest(manifest['rollback_contract_sha256'])
    issues = manifest['advisories']
    if not isinstance(issues, list) or not 1 <= len(issues) <= 64:
        raise Invalid('advisory count/type')
    if any(not isinstance(i, str) or len(i) > 96 or not IDENTIFIERS.fullmatch(i) for i in issues):
        raise Invalid('invalid advisory identifier')
    if issues != sorted(set(issues)):
        raise Invalid('advisories must be sorted and unique')
    for key in ('requires', 'conflicts', 'supersedes'):
        _digests(manifest[key], key)
    if set(manifest['requires']) & (set(manifest['conflicts']) | set(manifest['supersedes'])):
        raise Invalid('required fix is also conflicting or superseded')
    replacements = manifest['replacements']
    if not isinstance(replacements, list) or not 1 <= len(replacements) <= MAX_REPLACEMENTS:
        raise Invalid('replacement count/type')
    names, artifacts = [], []
    for replacement in replacements:
        fields(replacement, {'base', 'target', 'effect_contract_sha256', 'activation'}, 'replacement')
        digest(replacement['effect_contract_sha256'])
        if replacement['activation'] not in ('new-process', 'service-restart', 'relogin', 'node-reboot', 'offline-migration'):
            raise Invalid('unqualified activation mode')
        for side in ('base', 'target'):
            image = replacement[side]
            fields(image, IMAGE_FIELDS, 'replacement ' + side)
            if not isinstance(image['package'], str) or not NAME.fullmatch(image['package']):
                raise Invalid('invalid replacement package name')
            split_version(image['version'])
            if image['architecture'] not in ('amd64', 'all'):
                raise Invalid('unsupported replacement architecture')
            digest(image['artifact_sha256'])
            digest(image['source_manifest_sha256'])
            artifacts.append(image['artifact_sha256'])
        base, target = replacement['base'], replacement['target']
        if (base['package'], base['architecture']) != (target['package'], target['architecture']):
            raise Invalid('replacement changes package identity or architecture')
        if base['artifact_sha256'] == target['artifact_sha256']:
            raise Invalid('replacement has no artifact change')
        names.append((base['package'], base['architecture']))
    if names != sorted(set(names)):
        raise Invalid('replacements must be sorted and unique')
    if len(artifacts) != len(set(artifacts)):
        raise Invalid('duplicate or ambiguously reused artifact')
    if len(canonical(manifest)) > MAX_MANIFEST:
        raise Invalid('manifest size limit')
    return sorted(artifacts)


def _check_debs(manifest, artifacts):
    for replacement in manifest['replacements']:
        for side in ('base', 'target'):
            expected = replacement[side]
            data = artifacts[expected['artifact_sha256']]
            if not 1 <= len(data) <= MAX_ARTIFACT or sha(data) != expected['artifact_sha256']:
                raise Invalid('artifact size or digest mismatch')
            observed = inspect_bytes(data)
            identity = {k: expected[k] for k in ('package', 'version', 'architecture')}
            if observed['identity'] != identity:
                raise Invalid('original DEB identity differs from interim manifest')


def encode(manifest: dict, artifacts: dict[str, bytes]) -> bytes:
    order = check_manifest(manifest)
    if set(artifacts) != set(order):
        raise Invalid('artifact set differs from manifest')
    if any(not isinstance(v, bytes) for v in artifacts.values()):
        raise Invalid('artifact must be immutable bytes')
    if sum(map(len, artifacts.values())) > MAX_PAYLOAD:
        raise Invalid('aggregate payload limit')
    _check_debs(manifest, artifacts)
    header = canonical(manifest)
    pieces = [MAGIC, struct.pack('>I', len(header)), header]
    for key in order:
        data = artifacts[key]
        pieces.extend((bytes.fromhex(key), struct.pack('>Q', len(data)), data))
    return b''.join(pieces)


def decode(raw: bytes) -> tuple[dict, dict[str, bytes]]:
    if not isinstance(raw, bytes) or not len(MAGIC) + 4 <= len(raw) <= MAX_PACKAGE:
        raise Invalid('interim package size/type')
    if raw[:len(MAGIC)] != MAGIC:
        raise Invalid('interim package magic/version')
    position = len(MAGIC)
    length = struct.unpack_from('>I', raw, position)[0]
    position += 4
    if not 1 <= length <= MAX_MANIFEST or length > len(raw) - position:
        raise Invalid('interim manifest length')
    header = raw[position:position + length]
    manifest = parse_json(header)
    order = check_manifest(manifest)
    if canonical(manifest) != header:
        raise Invalid('noncanonical interim manifest')
    position += length
    artifacts, total = {}, 0
    for expected in order:
        if len(raw) - position < 40:
            raise Invalid('truncated artifact header')
        key = raw[position:position + 32].hex()
        size = struct.unpack_from('>Q', raw, position + 32)[0]
        position += 40
        total += size
        if key != expected or not 1 <= size <= MAX_ARTIFACT or total > MAX_PAYLOAD:
            raise Invalid('artifact order, identity or size')
        if size > len(raw) - position:
            raise Invalid('truncated artifact')
        artifacts[key] = raw[position:position + size]
        position += size
    if position != len(raw):
        raise Invalid('unlisted trailing payload')
    _check_debs(manifest, artifacts)
    return manifest, artifacts


def build_bytes(control: Path, artifacts_directory: Path, *, label: str | None = None) -> bytes:
    """Read the control once and bind the command label before any output write."""
    manifest = parse_json(read_file(control, MAX_MANIFEST))
    order = check_manifest(manifest)
    if label is not None and manifest['label'] != label:
        raise Invalid('command label differs from interim control')
    artifacts, total = {}, 0
    for key in order:
        data = read_file(artifacts_directory / (key + '.deb'), min(MAX_ARTIFACT, MAX_PAYLOAD - total))
        total += len(data)
        artifacts[key] = data
    return encode(manifest, artifacts)


def build_file(control: Path, artifacts_directory: Path, output: Path) -> str:
    """Local build-room API; cannot select an executable or change installed state."""
    raw = build_bytes(control, artifacts_directory)
    write_new(output, raw)
    return sha(raw)


def inspect_file(path: Path) -> dict:
    raw = read_file(path, MAX_PACKAGE)
    manifest, artifacts = decode(raw)
    return {'schema': 'org.niaos.interim-observation/v1', 'artifact_sha256': sha(raw),
            'manifest': manifest, 'contained_debs': len(artifacts),
            'publisher_authenticated': False, 'contracts_authenticated': False,
            'current_base_checked': False, 'execution_permit': False}
