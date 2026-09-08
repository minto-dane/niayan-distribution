#!/usr/bin/python3 -I
# SPDX-License-Identifier: MIT
"""Observe upload urgency and advisory fixes without installing or granting trust.

Urgency is upload metadata, not vulnerability severity. Advisory bytes supplied
offline are observations; this tool does not authenticate their publisher or
freshness, and never concludes that a package has no vulnerabilities.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from deb_archive import deb822, inspect_bytes, MAX_DEB
from debian_semantics import NAME, split_version, compare
from nia_common import Invalid, read_file, canonical, sha, digest, write_new

MAX_METADATA = 16 * 1024 * 1024
URGENCIES = frozenset(('low', 'medium', 'high', 'critical', 'emergency'))
SOURCE = re.compile(r'([a-z0-9][a-z0-9+.-]+)(?:\s+\(([^()\s]+)\))?\Z')


def source_identity(control: dict[str, str]) -> tuple[str, str]:
    name, version = control.get('package', ''), control.get('version', '')
    if not NAME.fullmatch(name):
        raise Invalid('invalid binary package name')
    split_version(version)
    match = SOURCE.fullmatch(control.get('source', name))
    if not match:
        raise Invalid('invalid source identity')
    source_version = match[2] or version
    split_version(source_version)
    return match[1], source_version


def upload_metadata(raw: bytes, control: dict[str, str], artifact_hash: str,
                    artifact_size: int) -> dict:
    """Require the exact binary in .changes; signature verification is separate."""
    digest(artifact_hash)
    paragraphs = deb822(raw, limit=MAX_METADATA, max_stanzas=1)
    if len(paragraphs) != 1:
        raise Invalid('one plain .changes stanza required')
    record = paragraphs[0]
    if record.get('format') != '1.8':
        raise Invalid('unsupported .changes format')
    expected_source = source_identity(control)
    match = SOURCE.fullmatch(record.get('source', ''))
    if not match or (match[1], match[2] or record.get('version')) != expected_source:
        raise Invalid('.changes source/version mismatch')
    if record.get('version') != control['version']:
        raise Invalid('.changes binary version mismatch')
    if control['package'] not in record.get('binary', '').split():
        raise Invalid('binary not declared in .changes')
    if control.get('architecture') not in record.get('architecture', '').split():
        raise Invalid('architecture not declared in .changes')
    names, matched = set(), []
    for line in record.get('checksums-sha256', '').splitlines():
        if not line.strip():
            continue
        row = line.split()
        if len(row) != 3 or not re.fullmatch('[0-9]{1,12}', row[1]):
            raise Invalid('invalid .changes checksum row')
        checksum, size, name = row
        digest(checksum)
        if '/' in name or name in ('.', '..') or name in names or len(names) >= 4096:
            raise Invalid('invalid or duplicate .changes filename')
        names.add(name)
        if checksum == artifact_hash and int(size) == artifact_size and name.endswith('.deb'):
            matched.append(name)
    if len(matched) != 1:
        raise Invalid('exact DEB hash/size absent or ambiguous in .changes')
    raw_urgency = record.get('urgency')
    urgency = None
    if raw_urgency is not None:
        if '\n' in raw_urgency or not raw_urgency.split():
            raise Invalid('invalid urgency')
        urgency = raw_urgency.split()[0].lower()
        if urgency not in URGENCIES:
            raise Invalid('unsupported urgency')
    return {'changes_sha256': sha(raw), 'artifact_filename': matched[0],
            'urgency': urgency, 'urgency_raw': raw_urgency,
            'distribution_raw': record.get('distribution'),
            'signature_verified': False, 'vulnerability_severity': None}


def advisory_matches(raw: bytes, source_name: str, source_version: str,
                     release: str = 'trixie') -> list[dict]:
    """Read source fix rows from the official DSA-list text grammar.

    Only exact release/source rows are compared. An absent match is unknown,
    never evidence of no security issues. This is not a complete tracker import.
    """
    if len(raw) > MAX_METADATA or release != 'trixie' or not NAME.fullmatch(source_name):
        raise Invalid('unsupported advisory size, release or source')
    split_version(source_version)
    try:
        text = raw.decode('utf-8')
    except UnicodeError as exc:
        raise Invalid('advisories must be UTF-8') from exc
    if any(ord(c) < 32 and c not in '\n\t\r' for c in text):
        raise Invalid('advisory control character')
    text = text.replace('\r\n', '\n')
    if '\r' in text:
        raise Invalid('advisory bare carriage return')
    result, seen = [], set()
    current, issue_ids, selected = None, [], []

    def finish():
        if current is not None:
            for fixed in selected:
                result.append({'advisory_id': current, 'mentioned_issue_ids': sorted(set(issue_ids)),
                               'release': release, 'source_package': source_name,
                               'fixed_source_version': fixed,
                               'version_relation': ('at-or-above-announced-fix'
                                                    if compare(source_version, fixed) >= 0
                                                    else 'below-announced-fix')})

    for line in text.splitlines():
        if len(line) > 65536:
            raise Invalid('advisory line limit')
        if not line.strip() or line.startswith('#'):
            continue
        if not line[0].isspace():
            match = re.fullmatch(r'\[[^\]\n]+\] (DSA-[0-9]+(?:-[0-9]+)?) .+', line)
            if not match or match[1] in seen or len(seen) >= 20000:
                raise Invalid('invalid, duplicate or excessive advisory header')
            finish()
            current, issue_ids, selected = match[1], [], []
            seen.add(current)
            continue
        if current is None:
            raise Invalid('orphan advisory row')
        row = line.strip()
        if row.startswith('{'):
            if not row.endswith('}'):
                raise Invalid('malformed advisory issue list')
            ids = row[1:-1].split()
            if any(not re.fullmatch(r'(?:CVE|CAN)-[0-9]{4}-[0-9]{4,}', item) for item in ids):
                raise Invalid('unsupported advisory issue identifier')
            issue_ids.extend(ids)
            if len(issue_ids) > 4096:
                raise Invalid('advisory issue count')
        elif row.startswith('[' + release + ']'):
            match = re.fullmatch(r'\[' + release + r'\] - (\S+) (\S+)', row)
            if not match:
                raise Invalid('unsupported target-release advisory row')
            if match[1] == source_name:
                split_version(match[2])
                if selected:
                    raise Invalid('ambiguous advisory source/release row')
                selected.append(match[2])
        elif row.startswith('[') or row.startswith('NOTE:'):
            continue
        else:
            raise Invalid('unsupported advisory row')
    finish()
    return result


def inspect_update(deb: bytes, changes: bytes | None = None,
                   advisories: bytes | None = None) -> dict:
    observed = inspect_bytes(deb)
    control = observed['fields']
    source_name, source_version = source_identity(control)
    return {'schema': 'org.niaos.update-metadata-observation/v1',
            'artifact_sha256': observed['artifact_sha256'], 'identity': observed['identity'],
            'source': {'name': source_name, 'version': source_version},
            'upload': None if changes is None else upload_metadata(changes, control, sha(deb), len(deb)),
            'advisories_sha256': None if advisories is None else sha(advisories),
            'advisory_matches': [] if advisories is None else advisory_matches(advisories, source_name, source_version),
            'security_assessment': 'not-established',
            'archive_authenticated': False, 'advisories_authenticated': False,
            'execution_permit': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deb', required=True)
    parser.add_argument('--changes', help='plain .changes payload; its signature is not verified here')
    parser.add_argument('--advisories', help='offline DSA-list text')
    parser.add_argument('--output', required=True, help='new output file only')
    args = parser.parse_args(argv)
    try:
        result = inspect_update(read_file(args.deb, MAX_DEB),
                                None if args.changes is None else read_file(args.changes, MAX_METADATA),
                                None if args.advisories is None else read_file(args.advisories, MAX_METADATA))
        write_new(args.output, canonical(result) + b'\n')
        return 0
    except (Invalid, OSError) as exc:
        print(f'update metadata: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
