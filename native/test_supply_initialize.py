# SPDX-License-Identifier: BSD-3-Clause
"""Finite initialization control and actual file publication boundaries."""
from collections import deque
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from supply_initialize import Phase, Rejected, advance, create, directory, open_input, publish


class SupplyInitializationTests(unittest.TestCase):
    def test_unbounded_paths_are_refused_before_open(self):
        with patch('supply_initialize.os.open') as opened:
            for path in ('relative/input', '/'+'x'*4096, '/a'*129):
                with self.assertRaises(Rejected):
                    directory(path)
            with self.assertRaises(Rejected):
                open_input('/'+'x'*4096)
            opened.assert_not_called()

    def close_failure(self, operation):
        real_close, real_open = os.close, os.open
        reused = []
        closed = []

        def fail_once(fd):
            real_close(fd)
            closed.append(fd)
            if not reused:
                replacement = real_open('/dev/null', os.O_RDONLY)
                self.assertEqual(replacement, fd)
                reused.append(replacement)
                raise OSError('injected error after kernel close')

        try:
            with patch('supply_initialize.os.close', side_effect=fail_once):
                with self.assertRaises(OSError):
                    operation()
            self.assertEqual(len(closed), 2, 'both original ownership and child FD released')
            self.assertNotEqual(closed[0], closed[1], 'reused FD was incorrectly closed')
            os.fstat(reused[0])
            with self.assertRaises(OSError):
                os.fstat(closed[1])
        finally:
            for fd in reused:
                real_close(fd)

    def test_directory_close_error_keeps_reused_fd(self):
        self.close_failure(lambda: directory('/usr'))

    def test_file_parent_close_error_releases_child(self):
        parent = os.open('/usr/bin', os.O_RDONLY | os.O_DIRECTORY)
        with patch('supply_initialize.directory', return_value=parent):
            self.close_failure(lambda: open_input('/usr/bin/env'))

    def test_control_history_is_one_way(self):
        initial = (Phase.NEW, 0, 0, 0, 0, False)
        pending = deque([initial])
        reached = {initial}
        while pending:
            before, verifies, policies, floors, completes, failed = pending.popleft()
            for event in Phase:
                try:
                    after = advance(before, event)
                except Rejected:
                    continue
                self.assertFalse(failed, 'failure reopened initialization')
                history = (after, verifies + (event is Phase.VERIFIED),
                           policies + (event is Phase.POLICY), floors + (event is Phase.FLOOR),
                           completes + (event is Phase.COMPLETE), failed or event is Phase.FAILED)
                _, v, p, f, c, _ = history
                self.assertTrue(0 <= c <= f <= p <= v <= 1)
                if history not in reached:
                    reached.add(history)
                    pending.append(history)
        self.assertEqual({row[0] for row in reached}, set(Phase))
        self.assertIn((Phase.COMPLETE, 1, 1, 1, 1, False), reached)
        self.assertIn((Phase.FAILED, 1, 1, 1, 0, True), reached)

    def exercise_publication(self, *, collision=False, interrupt=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'pending').mkdir()
            parent = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            source = os.open(root/'pending', os.O_RDONLY | os.O_DIRECTORY)
            try:
                create(source, 'supply.bin', b'protected public policy fixture', 0o444)
                before = (root/'pending/supply.bin').stat()
                if collision:
                    create(parent, 'supply.bin', b'preserve existing policy', 0o444)
                    with self.assertRaises(FileExistsError):
                        publish(source, parent, 'supply.bin')
                    self.assertEqual((root/'supply.bin').read_bytes(), b'preserve existing policy')
                    self.assertTrue((root/'pending/supply.bin').is_file())
                elif interrupt:
                    with patch('supply_initialize.os.unlink', side_effect=OSError('injected unlink failure')):
                        with self.assertRaises(OSError):
                            publish(source, parent, 'supply.bin')
                    self.assertEqual((root/'supply.bin').stat().st_nlink, 2)
                    self.assertEqual((root/'supply.bin').stat().st_ino, before.st_ino)
                    self.assertTrue((root/'pending/supply.bin').is_file())
                else:
                    publish(source, parent, 'supply.bin')
                    self.assertFalse((root/'pending/supply.bin').exists())
                    self.assertEqual((root/'supply.bin').stat().st_nlink, 1)
                    self.assertEqual((root/'supply.bin').stat().st_ino, before.st_ino)
            finally:
                os.close(source)
                os.close(parent)

    def test_no_replace_publication(self):
        self.exercise_publication()
        self.exercise_publication(collision=True)

    def test_interrupted_link_is_retained(self):
        self.exercise_publication(interrupt=True)


if __name__ == '__main__':
    unittest.main()
