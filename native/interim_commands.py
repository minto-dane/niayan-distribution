# SPDX-License-Identifier: MIT
"""Local epkg construction and emgr display, without installed-state authority.

The native artifact carries whole DEBs and typed contract references. Display
uses their actual inventory; it never invents installation state or file effects.
These development responses are not yet reference-output qualified.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import unicodedata

from interim_package import MAX_PACKAGE, Invalid, build_bytes, decode
from deb_archive import inspect_bytes
from nia_common import read_file, sha, write_new

MAX_DISPLAY = 16 * 1024 * 1024


def _directory(path: Path) -> None:
    """Create requested work directories with no symlink traversal."""
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in Path(os.path.abspath(path)).parts[1:]:
            try:
                os.mkdir(part, 0o700, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = child
    finally:
        os.close(fd)


def _display_text(value) -> str:
    # Original metadata can contain Unicode format characters. Do not turn
    # descriptions or paths into terminal control sequences or hidden labels.
    return ''.join(('\\u%04x' % ord(c)) if unicodedata.category(c).startswith('C') else c
                   for c in str(value))


def display(raw: bytes, verbosity: int) -> str:
    if type(verbosity) is not int or verbosity not in (1, 2, 3):
        raise Invalid('display verbosity')
    manifest, artifacts = decode(raw)
    lines, size = [], 0

    def line(name, value):
        nonlocal size
        text = name + ': ' + _display_text(value) + '\n'
        size += len(text.encode('utf-8'))
        if size > MAX_DISPLAY:
            raise Invalid('display output limit')
        lines.append(text)

    line('EFIX LABEL', manifest['label'])
    if verbosity >= 2:
        line('ABSTRACT', manifest['description'])
        modes = {r['activation'] for r in manifest['replacements']}
        line('REBOOT REQUIRED', 'yes' if 'node-reboot' in modes else
             'not established' if 'offline-migration' in modes else 'no')
        line('PRE-REQUISITES', ', '.join(manifest['requires']) or 'none')
        line('SUPERSEDE', ', '.join(manifest['supersedes']) or 'none')
        line('CONFLICTS', ', '.join(manifest['conflicts']) or 'none')
        line('ADVISORIES', ', '.join(manifest['advisories']))
    if verbosity == 3:
        line('PACKAGE SHA256', sha(raw))
        line('CREATED AT', manifest['created_at'])
        line('EXPIRES AT', manifest['expires_at'])
        line('SECURITY EPOCH', manifest['security_epoch'])
        line('ROLLBACK CONTRACT SHA256', manifest['rollback_contract_sha256'])
        line('PUBLISHER AUTHENTICATION', 'not verified')
    for replacement in manifest['replacements']:
        base, target = replacement['base'], replacement['target']
        observed = inspect_bytes(artifacts[target['artifact_sha256']])
        line('PACKAGE', target['package'])
        line('LEVEL', target['version'])
        if verbosity >= 2:
            line('BASE LEVEL', base['version'])
            line('ACTIVATION', replacement['activation'])
            for effect in observed['effect_members']:
                line('CONTROL EFFECT', effect['member'])
        if verbosity == 3:
            line('BASE SHA256', base['artifact_sha256'])
            line('TARGET SHA256', target['artifact_sha256'])
            line('EFFECT CONTRACT SHA256', replacement['effect_contract_sha256'])
        for index, entry in enumerate(observed['file_inventory'], 1):
            line('FILE NUMBER', index)
            line('LOCATION', '/' + entry['path'])
            if verbosity >= 2:
                line('FILE TYPE', entry['kind'])
            if verbosity == 3:
                for name in ('size', 'sha256', 'link'):
                    if entry.get(name) is not None and entry.get(name) != '':
                        line(name.upper(), entry[name])
    return ''.join(lines)


def execute_local(request) -> int:
    values = dict(request.values)
    try:
        if request.action == 'interim-build':
            label = request.operands[0]
            control = Path(values['e'])
            raw = build_bytes(control, control.parent, label=label)
            work = Path(values['w']) if 'w' in values else Path.home() / 'epkgwork'
            directory = work / label
            _directory(directory)
            output = directory / (label + '.' + sha(raw) + '.epkg')
            write_new(output, raw)
            print('Package file is: ' + _display_text(output))
        elif request.action == 'interim-display':
            path = Path(values['e'] if 'e' in values else request.operands[0])
            rendered = display(read_file(path, MAX_PACKAGE), int(values.get('v', '1')))
            sys.stdout.write(rendered)
        else:
            raise Invalid('unsupported local interim operation')
        return 0
    except (Invalid, OSError, RuntimeError) as exc:
        print(request.command + ': ' + _display_text(exc), file=sys.stderr)
        return 1
