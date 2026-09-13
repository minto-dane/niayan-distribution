#!/usr/bin/python3 -I
# SPDX-License-Identifier: BSD-3-Clause
"""Adopted-command dispatcher with a concrete accepted-catalog query path.

Installed changes remain refused until native planning and managed admission
are connected. There is no dispatch to pkg_worker, dpkg, a shell or a permissive
adapter. One bounded query child is owned and supervised at a time.
"""
from __future__ import annotations

from pathlib import Path
import fnmatch
import os
import select
import signal
import socket
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_query import Snapshot, query
from i18n import UI
from management_grammar import Request, UsageError
from management_receiver import Disposition, read_request, send_result
import management_result
from root_handoff import Rejected, now_ms

SOCKET = '/run/niaos/package.sock'
QUERY_ACTIONS = frozenset(('installed-list', 'installed-summary'))


def selectors(request: Request) -> tuple[str, ...]:
    patterns = request.operands or ('*',)
    if (len(patterns) > 64 or any(len(p) > 256 or '/' in p or '\\' in p for p in patterns)):
        raise Rejected('catalog-selector-limit')
    return patterns


def present(snapshot: Snapshot, request: Request, patterns: tuple[str, ...], ui: UI) -> str:
    rows = sorted((p for p in snapshot.packages if any(
        fnmatch.fnmatchcase(p.name, pattern) or fnmatch.fnmatchcase(p.name + ':' + p.architecture, pattern)
        for pattern in patterns)), key=lambda p: (p.name, p.architecture))
    if not rows and request.operands:
        raise Rejected('catalog-no-matching-fileset')
    colon = 'c' in request.flags
    lines: list[str] = []
    if 'q' not in request.flags:
        if colon:
            # Stable machine columns. Escape separators in native version epochs.
            lines.append('#Fileset:Level:State:Architecture')
        else:
            lines.append(ui.message('Fileset') + '\t' + ui.message('Level') + '\t'
                         + ui.message('State') + '\t' + ui.message('Architecture'))
    for p in rows:
        values = (p.name, p.version, 'COMMITTED', p.architecture)
        if colon:
            lines.append(':'.join(v.replace('\\', '\\\\').replace(':', '\\:') for v in values))
        else:
            lines.append('\t'.join(values))
    if not lines:
        return ui.message('No packages are recorded in the accepted catalog.')
    return '\n'.join(lines)


def serve(peer: socket.socket, recent: dict[int, list[int]]) -> None:
    request_id = uuid.uuid4().bytes
    ui = UI()
    peer_pidfd = -1
    try:
        peer.setblocking(False)
        if peer.getsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED) != 1:
            raise Rejected('management-credentials-required-before-accept')
        deadline = now_ms() + 2000
        poll = select.poll()
        poll.register(peer, select.POLLIN)
        if not poll.poll(2000) or now_ms() >= deadline:
            raise Rejected('management-request-timeout')
        command = read_request(peer, deadline)
        peer_pidfd = peer.getsockopt(socket.SOL_SOCKET, 77)
        os.set_inheritable(peer_pidfd, False)
        ui = UI.from_languages(command.languages)
        if command.request.action not in QUERY_ACTIONS or command.request.preview:
            send_result(peer, request_id, Disposition.REFUSED, ui.message(
                'This operation is not connected to native planning and admission. No package change was started.'))
            return
        patterns = selectors(command.request)
        current = now_ms()
        for uid in tuple(recent):
            recent[uid] = [expiry for expiry in recent[uid] if expiry > current]
            if not recent[uid]:
                del recent[uid]
        history = recent.get(command.actor_uid, [])
        if len(history) >= 4 or (not history and len(recent) >= 1024):
            send_result(peer, request_id, Disposition.REFUSED, ui.message(
                'Catalog queries are temporarily limited. No automatic retry was performed.'))
            return
        recent[command.actor_uid] = [*history, current + 10000]
        deadline = current + 120000
        snapshot = query(peer, deadline)
        text = present(snapshot, command.request, patterns, ui)
        if now_ms() >= deadline:
            raise Rejected('management-query-expired-before-delivery')
        poll = select.poll()
        poll.register(peer, select.POLLIN)
        poll.register(peer_pidfd, select.POLLIN)
        if poll.poll(0):
            raise Rejected('management-query-peer-ended-or-extra-request')
        management_result.send(peer, request_id, snapshot.descriptor, text)
    except UsageError as error:
        try:
            send_result(peer, request_id, Disposition.REFUSED, ui.message(error.message, **error.values))
        except (OSError, ValueError):
            pass
    except (OSError, ValueError, ExceptionGroup):
        # A failed query does not imply an empty catalog. Do not disclose trusted
        # layout paths or partial native output to the requesting account.
        try:
            send_result(peer, request_id, Disposition.REFUSED, ui.message(
                'The native catalog query could not complete. No package change was started.'))
        except (OSError, ValueError):
            pass
    finally:
        try:
            if peer_pidfd >= 0:
                os.close(peer_pidfd)
        finally:
            peer.close()


def main() -> None:
    if (os.getuid() or os.geteuid() or len(sys.argv) != 1
            or os.environ.get('LISTEN_PID') != str(os.getpid())
            or os.environ.get('LISTEN_FDS') != '1'):
        raise Rejected('management-service-activation')
    def stop(number: int, frame: object) -> None:
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    # Preserve the direct child until group cleanup; never inherit auto-reaping.
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    with socket.socket(fileno=3) as listener:
        if (listener.family != socket.AF_UNIX or listener.type != socket.SOCK_SEQPACKET
                or listener.getsockname() != SOCKET
                or listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) != 1
                or listener.getsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED) != 1):
            raise Rejected('management-service-listener')
        os.set_inheritable(listener.fileno(), False)
        recent: dict[int, list[int]] = {}
        while True:
            peer, _ = listener.accept()
            serve(peer, recent)


if __name__ == '__main__':
    main()
