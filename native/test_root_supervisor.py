# SPDX-License-Identifier: BSD-3-Clause
"""Focused failure-boundary checks; real effects belong to the VM checkpoint."""
import array
import os
import socket
import unittest
from unittest.mock import Mock, patch

from root_handoff import Rejected
from root_session_client import Phase, RootSession
from root_supervisor import Supervisor


class SupervisorFailures(unittest.TestCase):
    def test_disconnect_precedes_slow_observer_cleanup_even_on_error(self):
        calls = []
        session, operator, channel = Mock(), Mock(), Mock()
        def disconnect():
            calls.append('controller')
            raise OSError('simulated release failure')
        session.abort.side_effect = disconnect
        channel.close.side_effect = lambda: calls.append('handoff')
        operator.close.side_effect = lambda: calls.append('operator')
        supervisor = Supervisor.__new__(Supervisor)
        supervisor.consent = Mock()
        supervisor.session, supervisor.operator, supervisor.channels = session, operator, [channel]
        with self.assertRaises(BaseExceptionGroup):
            supervisor.close()
        self.assertEqual(calls, ['controller', 'handoff', 'operator'])
        self.assertTrue(supervisor.closed)
        self.assertEqual(supervisor.channels, [])

    def test_native_admission_refusal_disconnects_without_prepare(self):
        supervisor = Supervisor.__new__(Supervisor)
        supervisor.consent = Mock()
        supervisor.owner, supervisor.closed = os.getpid(), False
        supervisor.channels = []
        session, operator, admission = Mock(), Mock(), Mock()
        admission.check.side_effect = Rejected('native-supply-or-consent-unavailable')
        supervisor.session, supervisor.operator, supervisor.admission = session, operator, admission
        with patch('root_supervisor.os.getuid', return_value=0), patch('root_supervisor.os.geteuid', return_value=0):
            with self.assertRaisesRegex(Rejected, 'native-supply-or-consent-unavailable'):
                supervisor.wait_readable(99)
        session.prepare.assert_not_called()
        session.abort.assert_called_once()
        operator.close.assert_called_once()

    def test_unsolicited_controller_descriptors_are_closed_and_poison_session(self):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        fd = os.open('/dev/null', os.O_RDONLY | os.O_CLOEXEC)
        session = RootSession.__new__(RootSession)
        session.peer, session.phase, session.sender = left, Phase.PREPARING, 0
        before = len(os.listdir('/proc/self/fd'))
        try:
            right.sendmsg([b'untrusted'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [fd]))])
            with patch.object(session, 'current'), patch.object(session, 'physical') as physical:
                with self.assertRaises(Rejected):
                    session.receive()
                physical.assert_not_called()
            self.assertIs(session.phase, Phase.FAILED)
            self.assertEqual(len(os.listdir('/proc/self/fd')), before)
            os.fstat(fd)
        finally:
            left.close()
            right.close()
            os.close(fd)


if __name__ == '__main__':
    unittest.main()
