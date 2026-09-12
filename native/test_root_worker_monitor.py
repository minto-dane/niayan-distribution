# SPDX-License-Identifier: BSD-3-Clause
"""Owned subprocess fault tests; no host mounts or package state are changed."""
from collections import deque
import os
import select
import signal
import socket
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

from root_worker_monitor import Event, Phase, Rejected, run_worker, transition


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.peer, self.client = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.pidfd = os.pidfd_open(os.getpid())

    def tearDown(self):
        self.peer.close()
        self.client.close()
        os.close(self.pidfd)

    def run_child(self, code, deadline=5000, pidfd=None):
        return run_worker([sys.executable, '-I', '-c', code], b'request', (), self.peer,
                          self.pidfd if pidfd is None else pidfd,
                          int(time.clock_gettime(time.CLOCK_BOOTTIME) * 1000) + deadline)

    def test_normal_and_nonzero(self):
        self.assertEqual(self.run_child('import sys; print(sys.stdin.buffer.read().decode(), end="")'),
                         (0, b'request', b''))
        self.assertEqual(self.run_child('import sys; sys.stdin.buffer.read(); sys.exit(7)'), (7, b'', b''))

    def test_bounded_output(self):
        prefix = 'import os,sys; sys.stdin.buffer.read(); '
        self.assertEqual(len(self.run_child(prefix + 'os.write(1,b"x"*4096)')[1]), 4096)
        for fd, count in ((1, 4097), (2, 1025)):
            with self.subTest(fd=fd), self.assertRaisesRegex(Rejected, 'output-limit'):
                self.run_child(prefix + f'os.write({fd},b"x"*{count})')

    def test_deadline(self):
        started = time.monotonic()
        with self.assertRaisesRegex(Rejected, 'deadline'):
            self.run_child('import time; time.sleep(30)', deadline=150)
        self.assertLess(time.monotonic() - started, 3)

    def test_cancel_before_spawn(self):
        self.client.send(b'cancel')
        with patch('root_worker_monitor.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(Rejected, 'cancelled'):
                self.run_child('raise RuntimeError("must not run")')
            spawn.assert_not_called()

    def exercise_running_cancel(self, queued=False, requester_exit=False):
        # A pipe gives a deterministic boundary: both child and grandchild
        # exist, and the child is stopped. Cancellation must kill the group.
        read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
        owner = subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(30)'])
        owner_fd = os.pidfd_open(owner.pid)
        failures = []
        descendants = []
        code = ('import os,signal,subprocess,sys; sys.stdin.buffer.read(); '
                'child=subprocess.Popen([sys.executable,"-I","-c","import time; time.sleep(30)"]); '
                f'os.write({write_fd},str(child.pid).encode()); os.close({write_fd}); '
                'os.kill(os.getpid(),signal.SIGSTOP)')

        def cancel():
            try:
                ready = select.poll()
                ready.register(read_fd, select.POLLIN)
                if not ready.poll(3000):
                    raise RuntimeError('worker never reached cancellation boundary')
                descendant = os.pidfd_open(int(os.read(read_fd, 32)))
                descendants.append(descendant)
                if requester_exit:
                    owner.kill()
                elif queued:
                    self.client.send(b'cancel')
                else:
                    self.client.close()
            except BaseException as error:
                failures.append(error)

        thread = threading.Thread(target=cancel)
        thread.start()
        try:
            started = time.monotonic()
            with self.assertRaisesRegex(Rejected, 'cancelled'):
                run_worker([sys.executable, '-I', '-c', code], b'request', (write_fd,),
                           self.peer, owner_fd if requester_exit else self.pidfd,
                           int(time.clock_gettime(time.CLOCK_BOOTTIME) * 1000) + 5000)
            thread.join(4)
            self.assertFalse(thread.is_alive())
            self.assertEqual(failures, [])
            self.assertEqual(len(descendants), 1)
            exited = select.poll()
            exited.register(descendants[0], select.POLLIN)
            self.assertTrue(exited.poll(2000), 'descendant still executing')
            self.assertLess(time.monotonic() - started, 4)
        finally:
            thread.join(4)
            owner.kill()
            owner.wait(timeout=3)
            os.close(owner_fd)
            os.close(read_fd)
            os.close(write_fd)
            for descendant in descendants:
                try:
                    signal.pidfd_send_signal(descendant, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                finally:
                    os.close(descendant)

    def test_disconnect_stops_group(self):
        self.exercise_running_cancel()

    def test_queued_cancel_stops_group(self):
        self.exercise_running_cancel(queued=True)

    def test_requester_death_stops_group(self):
        self.exercise_running_cancel(requester_exit=True)

    def test_finite_lifecycle(self):
        # Exhaust actual runtime transition, with independent monotone history.
        # No depth cutoff. This checks control order, not kernel/interpreter I/O.
        initial = (Phase.NEW, 0, 0, 0, 0)
        seen = {initial}
        pending = deque([initial])
        while pending:
            phase, spawns, exits, stops, reaps = pending.popleft()
            for event in Event:
                try:
                    after = transition(phase, event)
                except Rejected:
                    continue
                history = (after, spawns + (event is Event.SPAWN), exits + (event is Event.EXIT),
                           stops + (event is Event.STOP), reaps + (event is Event.REAP))
                _, ns, ne, nt, nr = history
                self.assertTrue(0 <= nr <= nt <= ns <= 1)
                self.assertTrue(0 <= ne <= ns)
                self.assertFalse(reaps, 'reaped lifecycle reopened')
                self.assertFalse(stops and event is not Event.REAP)
                if history not in seen:
                    seen.add(history)
                    pending.append(history)
        self.assertEqual({item[0] for item in seen}, set(Phase))
        self.assertIn((Phase.REAPED, 1, 1, 1, 1), seen)
        self.assertIn((Phase.REAPED, 1, 0, 1, 1), seen)


if __name__ == '__main__':
    unittest.main()
