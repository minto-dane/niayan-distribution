# SPDX-License-Identifier: BSD-3-Clause
"""Public media commands on disposable original DEBs and real filesystem IO."""
import errno
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote

import media
from nia_common import Invalid, canonical, sha
from test_update_metadata import deb_fixture

BIN = Path(__file__).resolve().parent / 'bin'


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.raw = deb_fixture()
        (self.root / 'sample.deb').write_bytes(self.raw)

    def command(self, name, args, lang='C.UTF-8'):
        return subprocess.run([str(BIN / name), *map(str, args)], cwd=self.root,
                              env={'PATH': '', 'LC_ALL': lang}, capture_output=True,
                              encoding='utf-8', timeout=20)

    def test_real_index_and_listing_commands_preserve_originals(self):
        before = (self.root / 'sample.deb').stat()
        result = self.command('inutoc', [self.root])
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))
        body = json.loads((self.root / '.toc').read_bytes())
        self.assertEqual(body['artifacts'][0]['sha256'], sha(self.raw))
        self.assertFalse(body['archive_authenticated'])
        self.assertFalse(body['execution_permit'])
        self.assertFalse(body['installed_state_observed'])
        after = (self.root / 'sample.deb').stat()
        self.assertEqual((before.st_ino, before.st_mtime_ns, before.st_ctime_ns),
                         (after.st_ino, after.st_mtime_ns, after.st_ctime_ns))
        self.assertEqual((self.root / 'sample.deb').read_bytes(), self.raw)
        result = self.command('installp', ['-l', '-d', self.root], 'ja_JP.UTF-8')
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        self.assertIn('sample-bin', result.stdout)
        self.assertIn('パッケージ', result.stdout)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['.toc', 'sample.deb'])

    def test_index_is_reproducible_and_identical_rebuild_does_not_replace(self):
        media.inspect(self.root, rebuild=True)
        before = (self.root / '.toc').stat()
        original = (self.root / '.toc').read_bytes()
        os.utime(self.root / 'sample.deb', (100, 100))
        media.inspect(self.root, rebuild=True)
        self.assertEqual((self.root / '.toc').stat().st_ino, before.st_ino)
        self.assertEqual((self.root / '.toc').read_bytes(), original)
        with tempfile.TemporaryDirectory(prefix='independent-media-') as directory:
            second = Path(directory)
            (second / 'sample.deb').write_bytes(self.raw)
            media.inspect(second, rebuild=True)
            self.assertEqual((second / '.toc').read_bytes(), original)

    def test_stale_index_rejected_then_rebuilt_from_changed_original(self):
        media.inspect(self.root, rebuild=True)
        (self.root / 'sample.deb').write_bytes(deb_fixture({'version': '1:2.0-4'}))
        result = self.command('installp', ['-L', '-d', self.root])
        self.assertEqual((result.returncode, result.stdout), (1, ''))
        self.assertIn('[NIA-E-MEDIA-STALE]', result.stderr)
        self.assertIn('inutoc', result.stderr)
        self.assertEqual(self.command('inutoc', [self.root]).returncode, 0)
        result = self.command('geninstall', ['-L', '-d', self.root])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('1%3A2.0-4', result.stdout)

    def test_list_without_index_is_read_only_and_ignores_unrelated_files(self):
        (self.root / 'notes.txt').write_text('not a package')
        result = self.command('installp', ['-l', '-d', self.root])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / '.toc').exists())
        self.assertNotIn('notes.txt', result.stdout)

    def test_colon_output_roundtrips_epochs_unicode_controls_and_is_locale_independent(self):
        filename = '資料:100%.deb'
        (self.root / 'sample.deb').rename(self.root / filename)
        body = media.inspect(self.root)
        results = [self.command(command, ['-L', '-d', self.root], lang)
                   for command in ('installp', 'geninstall') for lang in ('C.UTF-8', 'ja_JP.UTF-8', 'fr_FR.UTF-8')]
        self.assertTrue(all(r.returncode == 0 and not r.stderr for r in results))
        self.assertEqual(len({r.stdout for r in results}), 1)
        row = [unquote(x) for x in results[0].stdout.splitlines()[1].split(':')]
        self.assertEqual(len(row), 6)
        self.assertEqual(row[1], '1:2.0-3+b1')
        self.assertEqual(row[4], filename)
        self.assertEqual(row[5], sha(self.raw))
        body['artifacts'][0]['description'] = 'line\nnext: % \x1b[31m'
        encoded = media.render(body, colon=True)
        self.assertEqual(len(encoded.splitlines()), 2)
        self.assertNotIn('\x1b', encoded)
        self.assertEqual(unquote(encoded.splitlines()[1].split(':')[3]), 'line\nnext: % \x1b[31m')
        self.assertNotIn('\x1b', media.render(body))

    def test_bad_image_preserves_previous_index(self):
        media.inspect(self.root, rebuild=True)
        original = (self.root / '.toc').read_bytes()
        (self.root / 'bad.deb').write_bytes(b'not a DEB')
        self.assertRaises(Invalid, media.inspect, self.root, rebuild=True)
        self.assertEqual((self.root / '.toc').read_bytes(), original)
        self.assertFalse(list(self.root.glob('.nia-toc-*')))

    def test_conflicting_and_duplicate_identities_are_rejected(self):
        for raw in (self.raw, deb_fixture(payload=b'different content')):
            (self.root / 'duplicate.deb').write_bytes(raw)
            self.assertRaises(Invalid, media.inspect, self.root, rebuild=True)
        self.assertFalse((self.root / '.toc').exists())

    def test_unsupported_or_linked_index_is_not_overwritten(self):
        target = self.root / 'unrelated'
        target.write_bytes(b'preserve')
        (self.root / '.toc').symlink_to(target)
        self.assertRaises(OSError, media.inspect, self.root, rebuild=True)
        self.assertEqual(target.read_bytes(), b'preserve')
        (self.root / '.toc').unlink()
        (self.root / '.toc').write_bytes(b'foreign format')
        self.assertRaises(Invalid, media.inspect, self.root, rebuild=True)
        self.assertEqual((self.root / '.toc').read_bytes(), b'foreign format')

    def test_image_links_fifo_and_linked_directory_are_rejected(self):
        (self.root / 'sample.deb').unlink()
        os.mkfifo(self.root / 'fifo.deb')
        self.assertRaises(Invalid, media.inspect, self.root)
        (self.root / 'fifo.deb').unlink()
        (self.root / 'data').write_bytes(self.raw)
        (self.root / 'linked.deb').symlink_to('data')
        self.assertRaises(OSError, media.inspect, self.root)
        with tempfile.TemporaryDirectory() as directory:
            link = Path(directory) / 'media'
            link.symlink_to(self.root)
            self.assertRaises(OSError, media.inspect, link)

    def test_directory_lock_and_write_permissions(self):
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            result = self.command('inutoc', [self.root])
            self.assertEqual(result.returncode, 1)
            self.assertIn('[NIA-E-BUSY]', result.stderr)
        finally:
            os.close(fd)
        self.root.chmod(0o777)
        self.assertRaises(Invalid, media.inspect, self.root, rebuild=True)
        self.assertTrue(media.inspect(self.root)['artifacts'])

    def test_detects_change_during_archive_observation(self):
        original = media.inspect_bytes
        def changed(raw):
            observed = original(raw)
            (self.root / 'added.deb').write_bytes(deb_fixture({'package': 'another-bin'}))
            return observed
        with patch('media.inspect_bytes', side_effect=changed):
            self.assertRaises(Invalid, media.inspect, self.root, rebuild=True)
        self.assertFalse((self.root / '.toc').exists())

    def test_write_and_sync_failure_preserve_complete_index(self):
        media.inspect(self.root, rebuild=True)
        before = (self.root / '.toc').read_bytes()
        (self.root / 'sample.deb').write_bytes(deb_fixture({'version': '1:2.0-4'}))
        for operation in ('write', 'fsync', 'replace'):
            with patch('media.os.' + operation, side_effect=OSError(errno.ENOSPC, 'test storage fault')):
                self.assertRaises(OSError, media.inspect, self.root, rebuild=True)
            self.assertEqual((self.root / '.toc').read_bytes(), before)
            self.assertFalse(list(self.root.glob('.nia-toc-*')))
        real_sync = os.fsync
        def final_sync(fd):
            import stat
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError(errno.EIO, 'test directory sync fault')
            return real_sync(fd)
        with patch('media.os.fsync', side_effect=final_sync):
            self.assertRaises(OSError, media.inspect, self.root, rebuild=True)
        self.assertNotEqual((self.root / '.toc').read_bytes(), before)
        self.assertEqual(media.inspect(self.root)['artifacts'][0]['identity']['version'], '1:2.0-4')

    def test_independent_resource_limits(self):
        for name, limit in (('MAX_IMAGES', 0), ('MAX_DIRECTORY_ENTRIES', 0), ('MAX_ARCHIVE', 1),
                            ('MAX_TOTAL', 1), ('MAX_INDEX', 512)):
            with self.subTest(name=name), patch.object(media, name, limit):
                self.assertRaises(Invalid, media.inspect, self.root, rebuild=True)
        self.assertFalse((self.root / '.toc').exists())

    def test_empty_media_has_deterministic_index_and_no_fake_package(self):
        (self.root / 'sample.deb').unlink()
        body = media.inspect(self.root, rebuild=True)
        self.assertEqual(body['artifacts'], [])
        self.assertEqual((self.root / '.toc').read_bytes(), canonical(body) + b'\n')
        self.assertEqual(len(media.render(body, colon=True).splitlines()), 1)


if __name__ == '__main__':
    unittest.main()
