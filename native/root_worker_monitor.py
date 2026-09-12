# SPDX-License-Identifier: BSD-3-Clause
"""Bounded execution for the controller's fixed, trusted root worker.

The caller owns the peer, peer pidfd and inherited input FDs. Only this function
owns/reaps the child. Cancellation does not undo effects or authorize a retry.
The service cgroup and independent bank sealing remain necessary containment.
"""
from collections.abc import Sequence
from enum import Enum, auto
import os
import select
import signal
import socket
import subprocess
import time


class Rejected(ValueError):
    """Execution failed or its effects are indeterminate."""


class Phase(Enum):
    NEW = auto()
    RUNNING = auto()
    EXITED = auto()
    STOPPED = auto()
    REAPED = auto()


class Event(Enum):
    SPAWN = auto()
    EXIT = auto()
    STOP = auto()
    REAP = auto()


def transition(phase: Phase, event: Event) -> Phase:
    if phase is Phase.NEW and event is Event.SPAWN:
        return Phase.RUNNING
    if phase is Phase.RUNNING and event is Event.EXIT:
        return Phase.EXITED
    if phase in (Phase.RUNNING, Phase.EXITED) and event is Event.STOP:
        return Phase.STOPPED
    if phase is Phase.STOPPED and event is Event.REAP:
        return Phase.REAPED
    raise Rejected('worker-lifecycle')


def _remaining(deadline_ms: int) -> float:
    remaining = deadline_ms - time.clock_gettime(time.CLOCK_BOOTTIME) * 1000
    if not 0 < remaining <= 600_000:
        raise Rejected('worker-deadline')
    return remaining


def _current(peer: socket.socket, pidfd: int, deadline_ms: int) -> None:
    _remaining(deadline_ms)
    guard = select.poll()
    guard.register(peer, select.POLLIN)
    guard.register(pidfd, select.POLLIN)
    # No second request is valid before the frozen response. Do not consume a
    # queued packet (and hence do not acquire any ancillary descriptors).
    if guard.poll(0):
        raise Rejected('worker-requester-ended-or-cancelled')


def run_worker(argv: Sequence[str], payload: bytes, inherited: tuple[int, ...],
               peer: socket.socket, pidfd: int, deadline_ms: int) -> tuple[int, bytes, bytes]:
    if not 0 < len(payload) <= 4096:
        raise Rejected('worker-input-size')
    _current(peer, pidfd, deadline_ms)
    phase = Phase.NEW
    child = subprocess.Popen(
        argv, pass_fds=inherited, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=True, bufsize=0,
        env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C.UTF-8'})
    phase = transition(phase, Event.SPAWN)
    streams = (child.stdin, child.stdout, child.stderr)
    output = bytearray()
    diagnostic = bytearray()
    try:
        if child.stdin is None or child.stdout is None or child.stderr is None:
            raise Rejected('worker-pipes')
        writer = child.stdin
        readers = {child.stdout.fileno(): (child.stdout, output, 4096),
                   child.stderr.fileno(): (child.stderr, diagnostic, 1024)}
        poll = select.poll()
        poll.register(peer, select.POLLIN)
        poll.register(pidfd, select.POLLIN)
        for stream in (writer, child.stdout, child.stderr):
            os.set_blocking(stream.fileno(), False)
        poll.register(writer, select.POLLOUT)
        for fd in readers:
            poll.register(fd, select.POLLIN)
        sent = 0
        # At most 600 seconds, 100 ms idle waits and bounded pipe progress.
        # A busy/broken descriptor cannot cause an unbounded readiness loop.
        for _ in range(16_384):
            _current(peer, pidfd, deadline_ms)
            if phase is Phase.RUNNING:
                # WNOWAIT retains the PID until killpg. Popen.poll()/wait()
                # here would reap it and permit a reused process-group ID.
                observed = os.waitid(os.P_PID, child.pid,
                                     os.WEXITED | os.WNOHANG | os.WNOWAIT)
                if observed is not None:
                    phase = transition(phase, Event.EXIT)
            if phase is Phase.EXITED and not readers:
                if sent != len(payload):
                    raise Rejected('worker-input-incomplete')
                break
            events = poll.poll(max(1, min(100, int(_remaining(deadline_ms)))))
            _current(peer, pidfd, deadline_ms)
            for fd, flags in events:
                if fd in readers:
                    stream, buffer, limit = readers[fd]
                    if flags & (select.POLLERR | select.POLLNVAL):
                        raise Rejected('worker-output-pipe')
                    try:
                        raw = os.read(fd, limit - len(buffer) + 1)
                    except BlockingIOError:
                        continue
                    if len(raw) + len(buffer) > limit:
                        raise Rejected('worker-output-limit')
                    if raw:
                        buffer.extend(raw)
                    else:
                        poll.unregister(fd)
                        del readers[fd]
                        stream.close()
                elif not writer.closed and fd == writer.fileno():
                    if flags & (select.POLLERR | select.POLLHUP | select.POLLNVAL):
                        raise Rejected('worker-input-pipe')
                    try:
                        sent += os.write(fd, payload[sent:])
                    except BlockingIOError:
                        continue
                    if sent == len(payload):
                        poll.unregister(fd)
                        writer.close()
        else:
            raise Rejected('worker-event-budget')
    finally:
        try:
            # The unreaped leader reserves this group ID. Also stop descendants
            # on the normal path before reaping; never signal a reaped PID.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            phase = transition(phase, Event.STOP)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired as error:
                raise Rejected('worker-stop-indeterminate') from error
            phase = transition(phase, Event.REAP)
        finally:
            close_errors: list[OSError] = []
            for owned in streams:
                if owned is not None:
                    try:
                        owned.close()
                    except OSError as error:
                        close_errors.append(error)
            if close_errors:
                raise Rejected('worker-pipe-close-indeterminate') from close_errors[0]
    _current(peer, pidfd, deadline_ms)
    if phase is not Phase.REAPED or child.returncode is None:
        raise Rejected('worker-not-reaped')
    return child.returncode, bytes(output), bytes(diagnostic)
