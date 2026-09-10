# SPDX-License-Identifier: BSD-3-Clause
"""Both real TUF and OpenPGP signatures must authenticate original DEB intake."""
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tests'))
import test_debian_trust as trust_tests
import test_repository as repository_tests
from test_repository_revalidation import clock_at
from archive_intake import authenticate
from nia_common import Invalid, canonical, sha


class ArchiveIntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        trust_tests.TrixieTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        trust_tests.TrixieTests.tearDownClass()

    def setUp(self):
        self.fixture = trust_tests.TrixieTests()
        self.fixture.setUp()
        temp = tempfile.TemporaryDirectory(prefix='nia-archive-supply-')
        self.addCleanup(temp.cleanup)
        self.cache = Path(temp.name)/'cache'
        self.remote = repository_tests.SignedRepository()
        self.remote.provision(self.cache)
        self.target = 'archives/trixie-amd64.json'
        self.envelope = {'schema': 'org.niaos.archive-supply/v1', 'security_epoch': 7,
                         'created_at': self.fixture.now-60, 'trust': copy.deepcopy(self.fixture.policy)}
        self.publish()

    def publish(self):
        self.raw = canonical(self.envelope)
        self.remote.targets[self.target] = self.raw
        self.remote.publish()

    def intake(self, client, **kwargs):
        return authenticate(client, self.target, self.fixture.root, self.fixture.fixture.keyring,
                            self.fixture.index, self.fixture.path, minimum_security_epoch=kwargs.get('floor', 7))

    def test_full_signed_chain_returns_native_original_and_control_bindings(self):
        with self.remote.client(self.cache) as client:
            result = self.intake(client)
        observed = result.observation()
        self.assertEqual(result.policy_bytes, self.raw)
        self.assertEqual(result.original, sha(self.fixture.fixture.deb))
        self.assertEqual(result.control, self.fixture.verify()['observation']['raw_control_sha256'])
        self.assertTrue(observed['repository_authenticated'])
        self.assertTrue(observed['debian_archive_authenticated'])
        for field in ('execution_permit', 'native_cas_bound', 'current_base_checked', 'contract_semantics_checked'):
            self.assertFalse(observed[field])
        self.assertFalse((self.fixture.fixture.root/'SCRIPT_WAS_EXECUTED').exists())

    def test_tuf_does_not_replace_archive_authentication(self):
        self.envelope['trust']['primary_fingerprints'] = ['A'*40]
        self.publish()
        with self.remote.client(self.cache) as client, self.assertRaises(Invalid):
            self.intake(client)

    def test_archive_authentication_does_not_replace_tuf(self):
        del self.remote.targets[self.target]
        self.remote.publish()
        with self.remote.client(self.cache) as client, self.assertRaises(Invalid):
            self.intake(client)

    def test_signed_policy_does_not_authorize_other_original_bytes(self):
        (self.fixture.root/self.fixture.path).write_bytes(b'changed')
        with self.remote.client(self.cache) as client, self.assertRaises(Invalid):
            self.intake(client)

    def test_epoch_is_checked_against_independent_floor(self):
        for floor in (8, True, 0):
            with self.subTest(floor=floor), self.remote.client(self.cache) as client, self.assertRaises(Invalid):
                self.intake(client, floor=floor)

    def test_legacy_policy_cannot_enter_the_shared_native_intake(self):
        self.envelope['trust'] = copy.deepcopy(self.fixture.fixture.policy)
        self.publish()
        with self.remote.client(self.cache) as client, self.assertRaisesRegex(Invalid, 'version 2'):
            self.intake(client)

    def test_policy_not_yet_valid(self):
        self.envelope['created_at'] = int(time.time())+3600
        self.publish()
        with self.remote.client(self.cache) as client, self.assertRaisesRegex(Invalid, 'currently valid'):
            self.intake(client)

    def test_policy_expired_after_archive_check(self):
        with self.remote.client(self.cache) as client:
            clock = SimpleNamespace(monotonic=time.monotonic, time=Mock(side_effect=[self.fixture.now, self.fixture.now+1800]))
            with patch('archive_intake.time', clock):
                with self.assertRaisesRegex(Invalid, 'deadline expired'):
                    self.intake(client)

    def test_backward_clock_is_rejected(self):
        with self.remote.client(self.cache) as client:
            clock = SimpleNamespace(monotonic=time.monotonic, time=Mock(side_effect=[self.fixture.now, self.fixture.now-1]))
            with patch('archive_intake.time', clock):
                with self.assertRaisesRegex(Invalid, 'time changed'):
                    self.intake(client)

    def test_expiry_during_final_recheck(self):
        with self.remote.client(self.cache) as client:
            clock = SimpleNamespace(monotonic=time.monotonic,
                                    time=Mock(side_effect=[self.fixture.now, self.fixture.now, self.fixture.now+1800]))
            with patch('archive_intake.time', clock):
                with self.assertRaisesRegex(Invalid, 'final recheck'):
                    self.intake(client)

    def test_policy_bytes_must_match_retained_authenticated_target(self):
        with self.remote.client(self.cache) as client:
            target = client.target
            def changed(*args):
                return target(*args)+b'\n'
            with patch.object(client, 'target', side_effect=changed), self.assertRaises(repository_tests.tuf_errors.RepositoryError):
                self.intake(client)

    def test_tuf_deadline_caps_archive_observation(self):
        expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        self.remote.role_expiries['timestamp'] = expiry
        self.publish()
        with self.remote.client(self.cache) as client:
            result = self.intake(client)
            self.assertEqual(result.valid_until, int(expiry.timestamp()))

    def test_tuf_expiry_during_archive_work_is_rejected(self):
        expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        self.remote.role_expiries['timestamp'] = expiry
        self.publish()
        with self.remote.client(self.cache) as client:
            revalidate = client.revalidate_target
            def later(*args):
                with clock_at(expiry + timedelta(seconds=1)):
                    return revalidate(*args)
            with patch.object(client, 'revalidate_target', side_effect=later):
                with self.assertRaises(repository_tests.tuf_errors.ExpiredMetadataError):
                    self.intake(client)

    def test_delegated_policy_deadline_caps_archive_observation(self):
        expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        del self.remote.targets[self.target]
        self.remote.delegation_pattern = 'archives/*'
        self.remote.delegated[self.target] = self.raw
        self.remote.role_expiries['fixes'] = expiry
        self.remote.publish()
        with self.remote.client(self.cache) as client:
            self.assertEqual(self.intake(client).valid_until, int(expiry.timestamp()))

    def test_root_is_rejected_before_any_supply_request(self):
        with self.remote.client(self.cache) as client:
            before = len(self.remote.requests)
            with patch('archive_intake.os.geteuid', return_value=0), self.assertRaisesRegex(Invalid, 'unprivileged'):
                self.intake(client)
            self.assertEqual(len(self.remote.requests), before)


if __name__ == '__main__':
    unittest.main()
