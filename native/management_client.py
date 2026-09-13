# SPDX-License-Identifier: BSD-3-Clause
"""Local adopted-command transport. No package writes or privilege escalation.

The fixed root service must plan/admit the request. A sealed presentation and
exact offer are confirmed on /dev/tty; stdin and environment never grant consent.
Only a final committed/preview response succeeds, never preparation or an ACK.
"""
from __future__ import annotations

import json
import os
import select
import socket
import stat
import sys
import termios

from i18n import UI, N_, write_text, languages
import management_result
from plan_consent import Offer, Rejected, now_ms, read_presentation, receive, release, response, presentation_text

SOCKET = '/run/niaos/package.sock'
MAX_REQUEST = 65536
MAX_RESULT = 65536


def connect() -> socket.socket:
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    peer: socket.socket | None = None
    try:
        for name in ('run', 'niaos'):
            info = os.fstat(directory)
            if info.st_uid or info.st_mode & 0o022:
                raise Rejected('unprotected-management-directory')
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
            previous, directory = directory, child
            os.close(previous)
        info = os.fstat(directory)
        endpoint = os.stat('package.sock', dir_fd=directory, follow_symlinks=False)
        if info.st_uid or info.st_mode & 0o022 or endpoint.st_uid or not stat.S_ISSOCK(endpoint.st_mode):
            raise Rejected('unprotected-management-endpoint')
        peer = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC)
        peer.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        peer.setblocking(False)
        peer.connect(f'/proc/self/fd/{directory}/package.sock')
        credentials = peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        if int.from_bytes(credentials[4:8], sys.byteorder, signed=True):
            raise Rejected('management-peer-not-root')
        return peer
    except BaseException:
        if peer is not None:
            peer.close()
        raise
    finally:
        try:
            os.close(directory)
        except BaseException:
            if peer is not None:
                peer.close()
            raise


def wait(peer: socket.socket, deadline: int) -> None:
    if now_ms() >= deadline:
        raise Rejected('management-deadline')
    poll = select.poll()
    poll.register(peer, select.POLLIN)
    for _ in range(2400):
        if now_ms() >= deadline:
            raise Rejected('management-deadline')
        if poll.poll(min(250, max(1, deadline - now_ms()))):
            return
    raise Rejected('management-wait-budget')


def confirm(peer: socket.socket, offer: Offer, text: str, ui: UI) -> bool:
    with open('/proc/sys/kernel/random/boot_id', encoding='ascii') as source:
        boot = bytes.fromhex(source.read(64).strip().replace('-', ''))
    if offer.boot != boot or not 0 < offer.deadline - now_ms() <= 120000:
        raise Rejected('management-offer-boot-or-expiry')
    # /dev/tty gives explicit human input even with -f lists or redirected stdin.
    # A missing tty refuses; no implicit -Y/quiet/environment bypass is added.
    fd = os.open('/dev/tty', os.O_RDWR | os.O_CLOEXEC | os.O_NOCTTY)
    try:
        if not os.isatty(fd):
            raise Rejected('management-confirmation-needs-terminal')
        termios.tcflush(fd, termios.TCIFLUSH)
        with os.fdopen(os.dup(fd), 'w', encoding='utf-8', errors='strict', closefd=True) as output:
            write_text(output, text + '\n')
            write_text(output, ui.message('Approve exactly this plan? Type yes to continue; any other answer cancels.') + '\n> ')
            output.flush()
        poll = select.poll()
        poll.register(fd, select.POLLIN)
        poll.register(peer, select.POLLIN)
        for _ in range(480):
            if now_ms() >= offer.deadline:
                raise Rejected('management-consent-expired')
            events = poll.poll(min(250, max(1, offer.deadline - now_ms())))
            if any(number == peer.fileno() for number, _ in events):
                raise Rejected('management-plan-ended-before-confirmation')
            if any(number == fd for number, _ in events):
                answer = os.read(fd, 16)
                return answer in (b'yes\n', b'yes\r\n')
        raise Rejected('management-consent-budget')
    finally:
        os.close(fd)


def execute(command: str, argv: list[str], ui: UI, *, preview: bool, read_only: bool) -> int:
    peer: socket.socket | None = None
    sent = confirmed = False
    offer: Offer | None = None
    sender = 0
    try:
        payload: dict[str, object] = dict(version=1, command=command, arguments=argv, languages=list(languages(os.environ)))
        request = (json.dumps(payload,
                   sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii')
        if len(request) > MAX_REQUEST or len(argv) > 4096:
            raise Rejected('management-request-too-large')
        peer = connect()
        # Delivery can be uncertain if the syscall fails. Never reconnect/retry.
        sent = True
        if peer.send(request, socket.MSG_DONTWAIT | socket.MSG_NOSIGNAL) != len(request):
            raise Rejected('management-request-delivery-indeterminate')
        deadline = now_ms() + 600000
        for _ in range(2):  # At most one offer, then one final response.
            wait(peer, deadline)
            owned: list[int] = []
            try:
                raw, actor, owned = receive(peer, MAX_RESULT)
                if actor[1] or sender not in (0, actor[0]):
                    raise Rejected('management-reply-sender')
                sender = actor[0]
                if raw.startswith(management_result.MAGIC):
                    if not read_only or preview or offer is not None or len(owned) != 1:
                        raise Rejected('management-unexpected-query-result')
                    text = management_result.read(raw, owned[0])
                    write_text(sys.stdout, text + '\n')
                    return 0
                if raw.startswith(b'NIAPLN01'):
                    if offer is not None or read_only or preview or len(owned) != 1:
                        raise Rejected('management-unexpected-plan-offer')
                    offer = Offer.decode(raw)
                    text = read_presentation(owned[0], offer)
                    release(owned)
                    confirmed = confirm(peer, offer, text, ui)
                    deadline = offer.deadline
                    reply = response(offer, confirmed)
                    if now_ms() >= deadline or peer.send(reply, socket.MSG_DONTWAIT | socket.MSG_NOSIGNAL) != len(reply):
                        raise Rejected('management-consent-delivery-indeterminate')
                    if not confirmed:
                        write_text(sys.stderr, ui.message('Plan cancelled; no confirmation was granted.') + '\n')
                        return 1
                    continue
                # Result: magic, disposition byte, seven zero bytes, request ID,
                # then UTF-8 presentation. No arbitrary JSON status coercion.
                if (owned or len(raw) < 33 or raw[:8] != b'NIARSL01' or any(raw[9:16])
                        or raw[8] not in (0, 1, 2, 3, 4) or not any(raw[16:32])):
                    raise Rejected('management-result-format')
                kind = raw[8]  # committed, refused, indeterminate, preview, read-only
                if offer is not None and raw[16:32] != offer.request:
                    raise Rejected('management-result-request')
                if ((kind == 0 and (not confirmed or read_only or preview))
                        or (kind == 3 and not preview) or (kind == 4 and not read_only)):
                    raise Rejected('management-result-without-required-consent')
                text = presentation_text(raw[32:])
                write_text(sys.stdout if kind in (0, 3, 4) else sys.stderr, text + '\n')
                return 0 if kind in (0, 3, 4) else 1
            finally:
                release(owned)
        raise Rejected('management-final-result-missing')
    except (OSError, ValueError, BaseExceptionGroup, KeyboardInterrupt) as error:
        message = (N_('The request outcome is unconfirmed. No automatic retry was performed.') if sent else
                   N_('The native package service is unavailable; no request was sent.'))
        write_text(sys.stderr, command + ': ' + ui.message(message) + '\n')
        if not isinstance(error, KeyboardInterrupt):
            write_text(sys.stderr, ui.message('Diagnostic: {reason}', reason=str(error)) + '\n')
        return 1
    finally:
        if peer is not None:
            peer.close()
