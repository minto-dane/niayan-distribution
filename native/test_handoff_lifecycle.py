# SPDX-License-Identifier: BSD-3-Clause
"""Control invariants and failure cleanup; ordinary local FDs, no root effects."""
import errno
import os
import select
import socket
import unittest
from unittest.mock import patch

from check_handoff_lifecycle import check
from root_handoff import Channel, Event, MAX_POLLS, Phase, Rejected, Scope, now_ms, transition


def fixture(phase=Phase.READY):
    channel = Channel.__new__(Channel)
    channel.peer, other = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    channel.pidfd = os.open('/dev/null', os.O_RDONLY)
    channel.descriptors = []
    channel.owner = os.getpid()
    channel.phase = phase
    channel.scope = Scope(*(bytes([1]) * 32 for _ in range(4)), bytes([2]) * 16, 1024, 1, now_ms() + 5000)
    channel.expected = channel.scope.wire()
    channel.child_pid = os.getpid()
    channel.child_uid = os.getuid()
    return channel, other


class LifecycleTests(unittest.TestCase):
    def test_exhaustive_control(self):
        result = check()
        self.assertGreater(result['configurations'], len(Phase))

    def test_model_detects_reopening_failure(self):
        def changed(phase, event):
            return Phase.READY if event is Event.FAIL else transition(phase, event)
        with self.assertRaisesRegex(AssertionError, 'terminal state reopened'):
            check(changed)

    def test_model_detects_completion_without_receive(self):
        def changed(phase, event):
            if phase is Phase.READY and event is Event.COMPLETE:
                return Phase.COMPLETING
            return transition(phase, event)
        with self.assertRaisesRegex(AssertionError, 'history order or replay'):
            check(changed)

    def test_closed_rejects_operations_without_io(self):
        channel, other = fixture()
        try:
            channel.close()
            with patch.object(channel, '_wait', side_effect=AssertionError('I/O after close')):
                for operation in (channel.receive, channel.complete):
                    with self.assertRaises(Rejected):
                        operation()
            channel.close()
        finally:
            channel.close()
            other.close()

    def test_release_error_still_closes_all_and_does_not_retry_reused_number(self):
        channel, other = fixture(Phase.RECEIVED)
        channel.descriptors = [os.open('/dev/null', os.O_RDONLY) for _ in range(2)]
        owned = [*channel.descriptors, channel.pidfd, channel.peer.fileno()]
        failing = channel.descriptors[0]
        actual_close = os.close
        reused = []
        visited = []
        def close(fd):
            visited.append(fd)
            actual_close(fd)
            if fd == failing:
                fresh = os.open('/dev/null', os.O_RDONLY)
                self.assertEqual(fresh, failing)
                reused.append(fresh)
                raise OSError(errno.EIO, 'injected error after Linux FD release')
        try:
            with patch('root_handoff.os.close', side_effect=close):
                with self.assertRaises(ExceptionGroup):
                    channel.close()
            self.assertEqual(visited, owned[:3])
            self.assertEqual(channel.phase, Phase.CLOSED)
            self.assertEqual(channel.descriptors, [])
            self.assertIsNone(channel.peer)
            self.assertEqual(channel.pidfd, -1)
            channel.close()
            os.fstat(reused[0])
            for fd in owned[1:]:
                with self.assertRaises(OSError):
                    os.fstat(fd)
        finally:
            channel.close()
            other.close()
            for fd in reused:
                actual_close(fd)

    def test_pidfd_close_error_does_not_skip_socket(self):
        channel, other = fixture()
        peer = channel.peer.fileno()
        pidfd = channel.pidfd
        actual_close = os.close
        def close(fd):
            actual_close(fd)
            if fd == pidfd:
                raise OSError(errno.EIO, 'pidfd close error')
        try:
            with patch('root_handoff.os.close', side_effect=close):
                with self.assertRaises(OSError):
                    channel.close()
            self.assertIsNone(channel.peer)
            with self.assertRaises(OSError):
                os.fstat(peer)
        finally:
            channel.close()
            other.close()

    def test_receive_failure_is_terminal(self):
        channel, other = fixture()
        try:
            with patch.object(channel, '_wait', side_effect=OSError(errno.EIO, 'read failure')):
                with self.assertRaises(OSError):
                    channel.receive()
            self.assertEqual(channel.phase, Phase.FAILED)
            for operation in (channel.receive, channel.complete):
                with self.assertRaises(Rejected):
                    operation()
        finally:
            channel.close()
            other.close()

    def test_completion_release_failure_prevents_reply(self):
        channel, other = fixture(Phase.RECEIVED)
        try:
            with patch.object(channel, '_release_inputs', side_effect=OSError(errno.EIO, 'release failure')):
                with self.assertRaises(OSError):
                    channel.complete()
            self.assertEqual(channel.phase, Phase.FAILED)
            with self.assertRaises(Rejected):
                channel.complete()
            other.setblocking(False)
            with self.assertRaises(BlockingIOError):
                other.recv(1)
        finally:
            channel.close()
            other.close()

    def test_cancel_arriving_during_writable_wait_prevents_reply(self):
        channel, other = fixture(Phase.RECEIVED)
        try:
            with patch.object(channel, '_alive'), patch.object(channel, '_wait', side_effect=lambda _: other.send(b'cancel')):
                with self.assertRaisesRegex(Rejected, 'cancel-or-disconnect'):
                    channel.complete()
            self.assertEqual(channel.phase, Phase.FAILED)
            other.setblocking(False)
            with self.assertRaises(BlockingIOError):
                other.recv(1)
        finally:
            channel.close()
            other.close()

    def test_poll_has_finite_call_budget(self):
        channel, other = fixture()
        try:
            with patch.object(channel, '_alive'), patch('root_handoff.select.poll') as factory:
                factory.return_value.poll.return_value = []
                with self.assertRaisesRegex(Rejected, 'poll-budget-exhausted'):
                    channel._wait(select.POLLIN)
                self.assertEqual(factory.return_value.poll.call_count, MAX_POLLS)
        finally:
            channel.close()
            other.close()


if __name__ == '__main__':
    unittest.main()
