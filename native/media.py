# SPDX-License-Identifier: MIT
"""Original DEB media inventory. No installed state, extraction or execution.

The .toc is an unsigned, reproducible cache, never a supply trust anchor. Every
listing re-inspects all original archives. Directory locks coordinate these
commands only; a caller must separately authenticate artifacts before admission.
"""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
import stat
import sys
import uuid
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from deb_archive import inspect_bytes
from nia_common import Invalid, canonical, directory_fd, parse_json, relative
from i18n import UI, N_, write_text
from diagnostics import public_error

MAX_ARCHIVE = 128 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024 * 1024
MAX_INDEX = 8 * 1024 * 1024
MAX_IMAGES = 4096
MAX_DIRECTORY_ENTRIES = 65536
SCHEMA = 'org.niaos.media-index/v1'


def _token(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid,
            s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _read(fd, name, limit):
    relative(name)
    if '/' in name:
        raise Invalid('flat media member required')
    child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
    try:
        before = os.fstat(child)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise Invalid('media member is not a bounded regular file')
        chunks, size = [], 0
        while True:
            chunk = os.read(child, min(1024 * 1024, limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > limit:
                raise Invalid('media member size limit')
        if size != before.st_size or _token(before) != _token(os.fstat(child)):
            raise Invalid('media changed during inspection')
        if _token(before) != _token(os.stat(name, dir_fd=fd, follow_symlinks=False)):
            raise Invalid('media changed during inspection')
        return b''.join(chunks), _token(before)
    finally:
        os.close(child)


def _names(fd):
    names = []
    count = 0
    with os.scandir(fd) as entries:
        for entry in entries:
            count += 1
            if count > MAX_DIRECTORY_ENTRIES:
                raise Invalid('media directory entry limit')
            if entry.name.endswith('.deb'):
                relative(entry.name)
                names.append(entry.name)
                if len(names) > MAX_IMAGES:
                    raise Invalid('media image count limit')
    return sorted(names)


def _scan(fd):
    directory = _token(os.fstat(fd))
    names = _names(fd)
    rows, tokens, identities = [], {}, set()
    total = index_bytes = 0
    for name in names:
        raw, token = _read(fd, name, MAX_ARCHIVE)
        total += len(raw)
        if total > MAX_TOTAL:
            raise Invalid('media total byte limit')
        observed = inspect_bytes(raw)
        identity = observed['identity']
        key = tuple(identity[k] for k in ('package', 'version', 'architecture'))
        if key in identities:
            raise Invalid('duplicate package version and architecture in media')
        identities.add(key)
        row = dict(filename=name, size=len(raw), sha256=observed['artifact_sha256'],
                   identity=identity, description=observed['fields'].get('description', ''),
                   raw_control_sha256=observed['raw_control_sha256'],
                   effect_members=observed['effect_members'],
                   trigger_declarations=observed['trigger_declarations'])
        rows.append(row)
        tokens[name] = token
        # Bound accumulated index metadata independently of archive storage.
        index_bytes += len(canonical(row))
        if index_bytes > MAX_INDEX - 1024:
            raise Invalid('media index size limit')
    body = dict(schema=SCHEMA, artifacts=rows, archive_authenticated=False,
                execution_permit=False, installed_state_observed=False)
    raw = canonical(body) + b'\n'
    if len(raw) > MAX_INDEX:
        raise Invalid('media index size limit')
    _unchanged(fd, names, tokens, directory=directory)
    return body, raw, names, tokens


def _unchanged(fd, names, tokens, *, directory=None):
    if _names(fd) != names or (directory is not None and _token(os.fstat(fd)) != directory):
        raise Invalid('media changed during inspection')
    for name, token in tokens.items():
        if _token(os.stat(name, dir_fd=fd, follow_symlinks=False)) != token:
            raise Invalid('media changed during inspection')


def _existing(fd):
    try:
        raw, token = _read(fd, '.toc', MAX_INDEX)
    except FileNotFoundError:
        return None, None
    value = parse_json(raw)
    if (type(value) is not dict or value.get('schema') != SCHEMA
            or canonical(value) + b'\n' != raw
            or value.get('archive_authenticated') is not False
            or value.get('execution_permit') is not False
            or value.get('installed_state_observed') is not False):
        raise Invalid('unsupported media index')
    return raw, token


def inspect(directory, *, rebuild=False):
    fd = directory_fd(directory)
    temporary = None
    try:
        fcntl.flock(fd, (fcntl.LOCK_EX if rebuild else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        if rebuild:
            st = os.fstat(fd)
            if st.st_uid != os.geteuid() or st.st_mode & 0o022:
                raise Invalid('media output directory must be owned and not group or world writable')
        old, old_token = _existing(fd)
        body, raw, names, tokens = _scan(fd)
        if _existing(fd) != (old, old_token):
            raise Invalid('media index changed during inspection')
        if not rebuild:
            if old is not None and old != raw:
                raise Invalid('media index is stale; rebuild with inutoc')
            return body
        if old == raw:
            return body
        temporary = '.nia-toc-' + uuid.uuid4().hex
        output = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=fd)
        try:
            view = memoryview(raw)
            while view:
                count = os.write(output, view)
                if count <= 0:
                    raise OSError('short media index write')
                view = view[count:]
            os.fchmod(output, 0o644)
            os.fsync(output)
        finally:
            os.close(output)
        _unchanged(fd, names, tokens)
        if _existing(fd) != (old, old_token):
            raise Invalid('media index changed during publication')
        os.replace(temporary, '.toc', src_dir_fd=fd, dst_dir_fd=fd)
        temporary = None
        os.fsync(fd)
        return body
    finally:
        try:
            if temporary is not None:
                os.unlink(temporary, dir_fd=fd)
        finally:
            os.close(fd)


def render(body, *, colon=False, ui=None):
    ui = ui or UI()
    lines = []
    if colon:
        # Native DEB media fields, not invented installed/licensing states.
        lines.append('#PACKAGE:LEVEL:ARCHITECTURE:DESCRIPTION:FILE:SHA256\n')
    else:
        lines.append(ui.message('{label}: {value}', label=ui.message('PUBLISHER AUTHENTICATION'),
                                value=ui.message('not verified')) + '\n')
    for row in body['artifacts']:
        identity = row['identity']
        values = (identity['package'], identity['version'], identity['architecture'],
                  row['description'], row['filename'], row['sha256'])
        if colon:
            # Percent escaping preserves epochs, newlines and Unicode losslessly.
            lines.append(':'.join(quote(v, safe='/+.-_~') for v in values) + '\n')
        else:
            for label, value in ((N_('PACKAGE'), values[0]), (N_('LEVEL'), values[1]),
                                 (N_('ARCHITECTURE'), values[2]),
                                 (N_('ABSTRACT'), values[3]), (N_('LOCATION'), values[4]),
                                 (N_('PACKAGE SHA256'), values[5])):
                lines.append(ui.message('{label}: {value}', label=ui.message(label), value=value) + '\n')
    output = ''.join(lines)
    if len(output.encode('utf-8')) > MAX_INDEX:
        raise Invalid('media display size limit')
    return output


def execute(request, *, ui=None):
    ui = ui or UI.from_environment()
    try:
        effective = request.delegate or request
        if effective.action == 'index-media':
            inspect(effective.operands[0], rebuild=True)
        elif effective.action in ('media-list', 'media-list-colon'):
            body = inspect(dict(effective.values)['d'])
            write_text(sys.stdout, render(body, colon=effective.action == 'media-list-colon', ui=ui))
        else:
            raise Invalid('unsupported media action')
        return 0
    except (Invalid, OSError, RuntimeError) as exc:
        write_text(sys.stderr, request.command + ': ' + public_error(exc, ui) + '\n')
        return 1
