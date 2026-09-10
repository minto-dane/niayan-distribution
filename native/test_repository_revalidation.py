# SPDX-License-Identifier: BSD-3-Clause
"""Fresh verification of retained real signed metadata, without remote access."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tuf.api import exceptions as tuf_errors
from tuf.api.metadata import Metadata
from tuf.ngclient import Updater

import repository
from nia_common import Invalid, canonical
from test_repository import SignedRepository


@contextmanager
def clock_at(moment):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment.astimezone(tz) if tz else moment.replace(tzinfo=None)
    # Replace the wall clock provider, never Updater's private trust state.
    clock = SimpleNamespace(time=lambda: moment.timestamp(), monotonic=time.monotonic)
    with patch('datetime.datetime', Clock), patch('repository.time', clock):
        yield


class RevalidationTests(unittest.TestCase):
    path = 'packages/sample.deb'

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.cache = Path(temporary.name) / 'cache'
        self.remote = SignedRepository()
        self.remote.provision(self.cache)

    def test_exact_target_revalidated_offline_without_checkpoint_write(self):
        with self.remote.client(self.cache) as client:
            raw = client.target(self.path)
            before = (self.cache/'checkpoint.json').read_bytes()
            self.remote.requests.clear()
            self.remote.files.clear()
            with patch('repository.Updater', wraps=Updater) as verifier:
                expiry = client.revalidate_target(self.path, raw)
            self.assertEqual(verifier.call_count, 1)
            self.assertEqual(expiry, int(self.remote.expires.timestamp()))
            self.assertEqual(self.remote.requests, [])
            self.assertEqual((self.cache/'checkpoint.json').read_bytes(), before)
            self.assertEqual(len(list(self.cache.iterdir())), 3)

    def test_each_top_role_bounds_observation(self):
        for role in ('timestamp', 'snapshot', 'targets'):
            with self.subTest(role=role):
                earlier = datetime.now(timezone.utc) + timedelta(minutes=10)
                self.remote.role_expiries = {role: earlier}
                self.remote.version += 1
                self.remote.publish()
                with self.remote.client(self.cache) as client:
                    raw = client.target(self.path)
                    self.assertEqual(client.revalidate_target(self.path, raw), int(earlier.timestamp()))

    def test_fresh_upstream_verifier_rejects_each_expired_top_role(self):
        for role in ('root', 'timestamp', 'snapshot', 'targets'):
            with self.subTest(role=role):
                remote = SignedRepository()
                expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
                if role == 'root':
                    remote.root.signed.expires = expiry
                    remote.root.sign(remote.keys['root'])
                    remote.bootstrap = remote.root.to_bytes()
                else:
                    remote.role_expiries[role] = expiry
                remote.publish()
                cache = self.cache.parent/role
                remote.provision(cache)
                with remote.client(cache) as client:
                    raw = client.target(self.path)
                    remote.requests.clear()
                    with clock_at(expiry + timedelta(seconds=1)):
                        with self.assertRaises(tuf_errors.ExpiredMetadataError):
                            client.revalidate_target(self.path, raw)
                    self.assertTrue(client.failed)
                    self.assertEqual(remote.requests, [])

    def test_delegated_expiry_is_used_only_when_visited(self):
        path = 'fixes/test.epkg'
        expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        self.remote.delegated[path] = b'delegated fixture'
        self.remote.role_expiries['fixes'] = expiry
        self.remote.publish()
        with self.remote.client(self.cache) as client:
            raw = client.target(path)
            ordinary = client.target(self.path)
            self.assertEqual(client.revalidate_target(path, raw), int(expiry.timestamp()))
            with clock_at(expiry + timedelta(seconds=1)):
                self.assertEqual(client.revalidate_target(self.path, ordinary), int(self.remote.expires.timestamp()))
                with self.assertRaises(tuf_errors.ExpiredMetadataError):
                    client.revalidate_target(path, raw)

    def test_root_rotation_uses_retained_root_without_bootstrap_reset(self):
        self.remote.root.signed.version = 2
        expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        self.remote.root.signed.expires = expiry
        self.remote.root.sign(self.remote.keys['root'])
        self.remote.files[self.remote.metadata_url+'2.root.json'] = self.remote.root.to_bytes()
        with self.remote.client(self.cache) as client:
            raw = client.target(self.path)
            self.remote.requests.clear()
            self.assertEqual(client.revalidate_target(self.path, raw), int(expiry.timestamp()))
            self.assertEqual(self.remote.requests, [])
            saved = repository.decode_checkpoint((self.cache/'checkpoint.json').read_bytes())
            self.assertEqual(Metadata.from_bytes(saved['root.json']).signed.version, 2)

    def test_different_bytes_rejected_and_session_poisoned(self):
        with self.remote.client(self.cache) as client:
            raw = client.target(self.path)
            with self.assertRaises(tuf_errors.RepositoryError):
                client.revalidate_target(self.path, raw+b'changed')
            for operation in (lambda: client.target(self.path), lambda: client.revalidate_target(self.path, raw)):
                with self.assertRaisesRegex(Invalid, 'not usable'):
                    operation()

    def test_absent_target_is_not_fetched(self):
        with self.remote.client(self.cache) as client:
            self.remote.requests.clear()
            with self.assertRaisesRegex(Invalid, 'absent'):
                client.revalidate_target('packages/absent.deb', b'absent')
            self.assertEqual(self.remote.requests, [])

    def test_checkpoint_replacement_before_revalidation_is_rejected(self):
        with self.remote.client(self.cache) as client:
            raw = client.target(self.path)
            checkpoint = self.cache/'checkpoint.json'
            checkpoint.write_bytes(checkpoint.read_bytes()+b'\n')
            with self.assertRaisesRegex(Invalid, 'checkpoint changed'):
                client.revalidate_target(self.path, raw)

    def test_checkpoint_change_during_revalidation_is_rejected(self):
        with self.remote.client(self.cache) as client:
            raw = client.target(self.path)
            def changed(*args, **kwargs):
                checkpoint = self.cache/'checkpoint.json'
                checkpoint.write_bytes(checkpoint.read_bytes()+b'\n')
                return Updater(*args, **kwargs)
            with patch('repository.Updater', side_effect=changed):
                with self.assertRaisesRegex(Invalid, 'checkpoint changed during revalidation'):
                    client.revalidate_target(self.path, raw)

    def test_repository_identity_change_is_rejected(self):
        with self.remote.client(self.cache) as client:
            raw = client.target(self.path)
            identity = dict(client.identity, targets_url='https://other.example.test/targets/')
            (self.cache/'repository.json').write_bytes(canonical(identity))
            with self.assertRaisesRegex(Invalid, 'identity changed'):
                client.revalidate_target(self.path, raw)

    def test_reservation_replacement_is_rejected(self):
        with self.remote.client(self.cache) as client:
            raw = client.target(self.path)
            lock = self.cache/'writer.lock'
            lock.unlink()
            lock.touch(mode=0o600)
            with self.assertRaisesRegex(Invalid, 'reservation changed'):
                client.revalidate_target(self.path, raw)

    def test_revalidation_consumes_shared_request_budget(self):
        with self.remote.client(self.cache) as client:
            raw = client.target(self.path)
            client.target_count = repository.MAX_REQUESTS
            with self.assertRaisesRegex(Invalid, 'aggregate target budget'):
                client.revalidate_target(self.path, raw)

    def test_expiry_at_return_boundary_is_rejected(self):
        with self.remote.client(self.cache) as client:
            raw = client.target(self.path)
            expiry = int(self.remote.expires.timestamp())
            wall = SimpleNamespace(monotonic=time.monotonic)
            with patch('repository.time', wall), patch.object(wall, 'time', create=True,
                                                             side_effect=[expiry-1, expiry]):
                with self.assertRaisesRegex(Invalid, 'expired during revalidation'):
                    client.revalidate_target(self.path, raw)

    def test_backward_clock_is_rejected(self):
        with self.remote.client(self.cache) as client:
            raw = client.target(self.path)
            now = int(time.time())
            wall = SimpleNamespace(monotonic=time.monotonic)
            with patch('repository.time', wall), patch.object(wall, 'time', create=True, side_effect=[now, now-1]):
                with self.assertRaisesRegex(Invalid, 'clock moved backward'):
                    client.revalidate_target(self.path, raw)

    def test_elapsed_session_is_rejected(self):
        with self.remote.client(self.cache) as client:
            raw = client.target(self.path)
            wall = SimpleNamespace(time=time.time, monotonic=lambda: client.started+repository.MAX_SESSION_SECONDS)
            with patch('repository.time', wall), self.assertRaisesRegex(Invalid, 'session expired'):
                client.revalidate_target(self.path, raw)

    def test_closed_session_cannot_be_revalidated(self):
        with self.remote.client(self.cache) as client:
            raw = client.target(self.path)
        with self.assertRaisesRegex(Invalid, 'not usable'):
            client.revalidate_target(self.path, raw)


if __name__ == '__main__':
    unittest.main()
