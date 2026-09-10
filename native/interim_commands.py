# SPDX-License-Identifier: BSD-3-Clause
"""Local epkg construction and emgr display, without installed-state authority.

The native artifact carries whole DEBs and typed contract references. Display
uses their actual inventory; it never invents installation state or file effects.
These development responses are not yet reference-output qualified.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

from i18n import UI, N_, write_text
from diagnostics import public_error
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


def display(raw: bytes, verbosity: int, *, ui=None) -> str:
    ui = ui or UI()
    if type(verbosity) is not int or verbosity not in (1, 2, 3):
        raise Invalid('display verbosity')
    manifest, artifacts = decode(raw)
    lines, size = [], 0

    def line(name, value):
        nonlocal size
        text = ui.message('{label}: {value}', label=ui.message(name), value=value) + '\n'
        size += len(text.encode('utf-8'))
        if size > MAX_DISPLAY:
            raise Invalid('display output limit')
        lines.append(text)

    line(N_('EFIX LABEL'), manifest['label'])
    if verbosity >= 2:
        line(N_('ABSTRACT'), manifest['description'])
        modes = {r['activation'] for r in manifest['replacements']}
        line(N_('REBOOT REQUIRED'), ui.context('reboot-required', 'yes') if 'node-reboot' in modes else
             ui.message('not established') if 'offline-migration' in modes else ui.context('reboot-required', 'no'))
        line(N_('PRE-REQUISITES'), ', '.join(manifest['requires']) or ui.message('none'))
        line(N_('SUPERSEDE'), ', '.join(manifest['supersedes']) or ui.message('none'))
        line(N_('CONFLICTS'), ', '.join(manifest['conflicts']) or ui.message('none'))
        line(N_('ADVISORIES'), ', '.join(manifest['advisories']))
    if verbosity == 3:
        line(N_('PACKAGE SHA256'), sha(raw))
        line(N_('CREATED AT'), manifest['created_at'])
        line(N_('EXPIRES AT'), manifest['expires_at'])
        line(N_('SECURITY EPOCH'), manifest['security_epoch'])
        line(N_('ROLLBACK CONTRACT SHA256'), manifest['rollback_contract_sha256'])
        line(N_('PUBLISHER AUTHENTICATION'), ui.message('not verified'))
    for replacement in manifest['replacements']:
        base, target = replacement['base'], replacement['target']
        observed = inspect_bytes(artifacts[target['artifact_sha256']])
        line(N_('PACKAGE'), target['package'])
        line(N_('LEVEL'), target['version'])
        if verbosity >= 2:
            line(N_('BASE LEVEL'), base['version'])
            line(N_('ACTIVATION'), replacement['activation'])
            for effect in observed['effect_members']:
                line(N_('CONTROL EFFECT'), effect['member'])
        if verbosity == 3:
            line(N_('BASE SHA256'), base['artifact_sha256'])
            line(N_('TARGET SHA256'), target['artifact_sha256'])
            line(N_('EFFECT CONTRACT SHA256'), replacement['effect_contract_sha256'])
        for index, entry in enumerate(observed['file_inventory'], 1):
            line(N_('FILE NUMBER'), index)
            line(N_('LOCATION'), '/' + entry['path'])
            if verbosity >= 2:
                line(N_('FILE TYPE'), entry['kind'])
            if verbosity == 3:
                for name, label in (('size', N_('SIZE')), ('sha256', N_('SHA256')), ('link', N_('LINK'))):
                    if entry.get(name) is not None and entry.get(name) != '':
                        line(label, entry[name])
    return ''.join(lines)


def execute_local(request, *, ui=None) -> int:
    ui = ui or UI.from_environment()
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
            write_text(sys.stdout, ui.message('Package file is: {path}', path=output) + '\n')
        elif request.action == 'interim-display':
            path = Path(values['e'] if 'e' in values else request.operands[0])
            rendered = display(read_file(path, MAX_PACKAGE), int(values.get('v', '1')), ui=ui)
            write_text(sys.stdout, rendered)
        else:
            raise Invalid('unsupported local interim operation')
        return 0
    except (Invalid, OSError, RuntimeError) as exc:
        write_text(sys.stderr, request.command + ': ' + public_error(exc, ui) + '\n')
        return 1
