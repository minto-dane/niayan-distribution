# SPDX-License-Identifier: BSD-3-Clause
"""Finite control/history and owned descriptor cleanup, no system mutation."""
from collections import deque
import os
import unittest
from unittest.mock import patch

import operator_guard as guard


class OperatorGuardTests(unittest.TestCase):
    def test_all_control_histories(self):
        initial = (guard.Phase.NEW, 0, 0, 0, False)
        pending = deque([initial])
        reached = {initial}
        while pending:
            phase, sequence, requested, observed, terminal = pending.popleft()
            for event in ('request', 'observe', 'fail', 'close'):
                try:
                    after, count = guard.advance(phase, event, sequence)
                except guard.Rejected:
                    continue
                self.assertTrue(not terminal or event == 'close')
                sends = requested + (event == 'request')
                reads = observed + (event == 'observe')
                self.assertEqual(count, sends)
                self.assertLessEqual(reads, sends)
                self.assertLessEqual(sends, reads + 1)
                self.assertLessEqual(sends, guard.MAX_CHECKS)
                state = after, count, sends, reads, terminal or event in ('fail', 'close')
                if state not in reached:
                    reached.add(state)
                    pending.append(state)
        self.assertIn((guard.Phase.OBSERVED, guard.MAX_CHECKS, guard.MAX_CHECKS, guard.MAX_CHECKS, False), reached)
        self.assertIn((guard.Phase.FAILED, 1, 1, 0, True), reached)

    def test_helper_directory_close_does_not_close_reused_number(self):
        real_open, real_close = os.open, os.close
        reused = []
        directories = []
        def opened(path, flags, **kwargs):
            # Read only existing root-owned directories; no fixture trust input.
            fd = real_open('/usr' if path in ('usr', 'libexec', 'nia') else path, flags, **kwargs)
            directories.append(fd)
            return fd
        def closed(fd):
            real_close(fd)
            if len(directories) == 2 and not reused:
                replacement = real_open('/dev/null', os.O_RDONLY)
                self.assertEqual(fd, replacement)
                reused.append(replacement)
                raise OSError('injected release failure')
        try:
            with patch.object(guard.os, 'open', side_effect=opened), patch.object(guard.os, 'close', side_effect=closed):
                with self.assertRaises(OSError):
                    guard.executable()
            os.fstat(reused[0])
            with self.assertRaises(OSError):
                os.fstat(directories[1])
        finally:
            for fd in reused:
                real_close(fd)

    def test_unprivileged_constructor_refuses_before_spawn(self):
        with patch.object(guard.os, 'getuid', return_value=1000), patch.object(guard.subprocess, 'Popen', side_effect=AssertionError('spawn')):
            with self.assertRaises(guard.Rejected):
                guard.OperatorGuard(None, bytes([1])*32, bytes([2])*16, guard.now_ms()+1000, interactive=False)


if __name__ == '__main__':
    unittest.main()
