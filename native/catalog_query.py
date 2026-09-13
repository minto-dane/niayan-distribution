# SPDX-License-Identifier: BSD-3-Clause
"""Root-owned query bridge to the concrete, nonroot native catalog reader.

Only administrator-configured paths reach the child. No request operand becomes
an input path or a shell argument. A complete successful native response and EOF
are required before a snapshot can be presented; partial output is discarded.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import pwd
import re
import select
import signal
import socket
import struct
import subprocess
from typing import cast

import native_helper
from root_handoff import Rejected, now_ms
from supply_initialize import protected

CONFIG = '/etc/niaos/package-query.json'
LIMIT = 64 * 1024 * 1024


@dataclass(frozen=True)
class Package:
    original: bytes
    name: str
    version: str
    architecture: str
    essential: bool
    protected: bool
    installed_kib: int | None


@dataclass(frozen=True)
class Snapshot:
    descriptor: bytes
    generation: int
    started: int
    finished: int
    packages: tuple[Package, ...]


def layout() -> tuple[str, str, str, bytes]:
    raw = protected(CONFIG, 16384)
    parsed = cast(object, json.loads(raw))
    if not isinstance(parsed, dict):
        raise Rejected('catalog-layout-object')
    value = cast(dict[str, object], parsed)
    if (set(value) != {'version', 'root', 'state', 'store', 'root_id'}
            or type(value['version']) is not int or value['version'] != 1
            or json.dumps(value, sort_keys=True, separators=(',', ':')).encode('ascii') + b'\n' != raw):
        raise Rejected('catalog-layout-format')
    paths: list[str] = []
    for name in ('root', 'state', 'store'):
        path = value[name]
        if (not isinstance(path, str) or not path.startswith('/') or len(path) > 4096
                or len(path.split('/')) > 128 or any(p in ('', '.', '..') for p in path.split('/')[1:])
                or any(ord(c) < 32 or ord(c) == 127 for c in path)):
            raise Rejected('catalog-layout-path')
        paths.append(path)
    if len(set(paths)) != 3:
        raise Rejected('catalog-layout-overlap')
    root_id = value['root_id']
    if not isinstance(root_id, str) or not re.fullmatch('[0-9a-f]{32}', root_id) or root_id == '0' * 32:
        raise Rejected('catalog-layout-root')
    return paths[0], paths[1], paths[2], bytes.fromhex(root_id)


def decode(raw: bytes, root: bytes, started: int, deadline: int) -> Snapshot:
    if not 224 <= len(raw) <= LIMIT or raw[:8] != b'NIAQRY01':
        raise Rejected('catalog-query-frame')
    d = raw[8:200]
    generation = int.from_bytes(d[104:112], 'big')
    if (d[:8] != b'NIAPUB01' or d[8:24] != root or not any(d[24:40]) or d[24:40] == root
            or not any(d[40:72]) or not any(d[72:104]) or not 0 < generation <= 2**63 - 1
            or ((generation == 1) != (not any(d[112:144]))) or any(d[144:160])
            or hashlib.sha256(d[:160]).digest() != d[160:]):
        raise Rejected('catalog-query-descriptor')
    begin, end, count = struct.unpack('>QQQ', raw[200:224])
    if not started <= begin <= end < deadline or end > now_ms() or count > 4096:
        raise Rejected('catalog-query-clock-or-count')
    offset = 224
    packages: list[Package] = []
    identities: set[tuple[str, str]] = set()
    previous = bytes(32)
    for _ in range(count):
        if offset + 48 > len(raw):
            raise Rejected('catalog-query-short-row')
        prefix = raw[offset:offset + 48]
        offset += 48
        original = prefix[:32]
        size = int.from_bytes(prefix[32:40], 'big')
        if (original <= previous or any(v not in (0, 1) for v in prefix[40:43])
                or any(prefix[43:]) or size > 2**63 - 1 or (not prefix[42] and size)):
            raise Rejected('catalog-query-row')
        previous = original
        fields: list[str] = []
        for _ in range(3):
            if offset + 2 > len(raw):
                raise Rejected('catalog-query-short-field')
            length = int.from_bytes(raw[offset:offset + 2], 'big')
            offset += 2
            if not 0 < length <= 4096 or offset + length > len(raw):
                raise Rejected('catalog-query-field-size')
            text = raw[offset:offset + length].decode('ascii', errors='strict')
            if any(ord(c) < 33 or ord(c) > 126 for c in text):
                raise Rejected('catalog-query-field-control')
            fields.append(text)
            offset += length
        name, version, architecture = fields
        identity = (name, architecture)
        if identity in identities:
            raise Rejected('catalog-query-duplicate-package')
        identities.add(identity)
        packages.append(Package(original, name, version, architecture,
            bool(prefix[40]), bool(prefix[41]), size if prefix[42] else None))
    if offset != len(raw):
        raise Rejected('catalog-query-trailing-data')
    return Snapshot(d, generation, begin, end, tuple(packages))


def query(peer: socket.socket, deadline: int) -> Snapshot:
    """Poll cancellation and original time while one native process observes."""
    started = now_ms()
    if os.getuid() or os.geteuid() or not 0 < deadline - started <= 120000:
        raise Rejected('catalog-query-context')
    root, state, store, identity = layout()
    account = pwd.getpwnam('nia-pkg')
    if account.pw_uid <= 0 or account.pw_gid <= 0:
        raise Rejected('catalog-query-account')
    child: subprocess.Popen[bytes] | None = None
    peer_pidfd = pidfd = -1
    raw = bytearray()
    try:
        peer_pidfd = peer.getsockopt(socket.SOL_SOCKET, 77)
        os.set_inheritable(peer_pidfd, False)
        pinned = native_helper.executable('pkg_catalog_query')
        try:
            child = subprocess.Popen(['/usr/libexec/nia/pkg_catalog_query', root, state, store,
                identity.hex(), str(deadline)], executable=f'/proc/self/fd/{pinned}',
                pass_fds=(pinned,), user=account.pw_uid, group=account.pw_gid, extra_groups=[],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                cwd='/', start_new_session=True, bufsize=0, umask=0o077,
                env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'})
        finally:
            os.close(pinned)
        pidfd = os.pidfd_open(child.pid)
        os.set_inheritable(pidfd, False)
        assert child.stdout is not None
        output = child.stdout.fileno()
        os.set_blocking(output, False)
        poll = select.poll()
        for fd in (peer.fileno(), peer_pidfd, pidfd, output):
            poll.register(fd, select.POLLIN)
        eof = False
        for _ in range(16384):
            if now_ms() >= deadline:
                raise Rejected('catalog-query-deadline')
            events = poll.poll(min(250, max(1, deadline - now_ms())))
            if any(fd in (peer.fileno(), peer_pidfd) or flags & select.POLLNVAL for fd, flags in events):
                raise Rejected('catalog-query-cancelled')
            if any(fd == output for fd, _ in events):
                data = os.read(output, min(65536, LIMIT + 1 - len(raw)))
                if not data:
                    eof = True
                    poll.unregister(output)
                else:
                    raw.extend(data)
                    if len(raw) > LIMIT:
                        raise Rejected('catalog-query-output-limit')
            if eof:
                result = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
                if result is not None:
                    if result.si_code != os.CLD_EXITED or result.si_status != 0:
                        raise Rejected('catalog-query-native-refused')
                    # Do not reap here: cleanup retains the leader across killpg.
                    return decode(bytes(raw), identity, started, deadline)
        raise Rejected('catalog-query-event-budget')
    finally:
        failures: list[BaseException] = []
        if child is not None:
            try:
                os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=5)
            except BaseException as error:
                failures.append(error)
            if child.stdout is not None:
                try:
                    child.stdout.close()
                except BaseException as error:
                    failures.append(error)
        for fd in (pidfd, peer_pidfd):
            if fd >= 0:
                try:
                    os.close(fd)
                except BaseException as error:
                    failures.append(error)
        if failures:
            raise BaseExceptionGroup('catalog-query-cleanup-indeterminate', failures)
