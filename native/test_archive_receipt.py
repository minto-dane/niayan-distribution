# SPDX-License-Identifier: MIT
"""A real scoped signer only receives fully authenticated archive observations."""
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import struct
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tests'))
import test_debian_trust as trust_tests
import test_repository as repository_tests
from archive_receipt import issue, scope, DOMAIN, MAGIC, WIRE_SIZE
from nia_common import Invalid, canonical, sha


class ReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        trust_tests.TrixieTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        trust_tests.TrixieTests.tearDownClass()

    def setUp(self):
        self.fixture = trust_tests.TrixieTests()
        self.fixture.setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.cache = Path(temporary.name)/'cache'
        self.remote = repository_tests.SignedRepository()
        self.remote.provision(self.cache)
        self.target = 'archives/trixie-amd64.json'
        self.policy = canonical({'schema': 'org.niaos.archive-supply/v1', 'security_epoch': 7,
                                 'created_at': self.fixture.now-60, 'trust': copy.deepcopy(self.fixture.policy)})
        self.remote.targets[self.target] = self.policy
        self.remote.publish()
        self.key = Ed25519PrivateKey.generate()
        self.public_key = self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.sign = Mock(side_effect=self.key.sign)

    def issue(self, client, **kwargs):
        args = dict(minimum_security_epoch=7, maximum_lifetime_seconds=300,
                    public_key=self.public_key, sign=self.sign)
        args.update(kwargs)
        return issue(client, self.target, self.fixture.root, self.fixture.fixture.keyring,
                     self.fixture.index, self.fixture.path, **args)

    def test_full_observation_has_canonical_native_signature(self):
        with self.remote.client(self.cache) as client:
            receipt = self.issue(client)
            expected_scope = scope(client, self.target)
        wire = receipt.wire
        self.assertEqual(len(wire), WIRE_SIZE)
        self.assertEqual(wire[:8], MAGIC)
        self.assertEqual(wire[8:40].hex(), expected_scope)
        self.assertEqual(wire[40:72].hex(), sha(self.policy))
        self.assertEqual(wire[72:104].hex(), sha(self.fixture.fixture.deb))
        self.assertEqual(wire[104:136].hex(), self.fixture.verify()['observation']['raw_control_sha256'])
        self.assertEqual(wire[136:168].hex(), sha(self.fixture.signed))
        self.assertEqual(wire[168:200].hex(), sha(self.fixture.fixture.packed))
        self.assertEqual(wire[200:232].hex(), sha(self.fixture.fixture.keyring))
        epoch, checked, expires = struct.unpack('>QQQ', wire[232:256])
        self.assertEqual(epoch, 7)
        self.assertLessEqual(checked, time.time())
        self.assertEqual(expires-checked, 300)
        self.assertEqual(receipt.policy_bytes, self.policy)
        self.key.public_key().verify(wire[256:], struct.pack('>H', len(DOMAIN))+DOMAIN+wire[:256])
        self.assertEqual(self.sign.call_count, 1)

    def test_bad_original_never_reaches_signer(self):
        (self.fixture.root/self.fixture.path).write_bytes(b'changed')
        with self.remote.client(self.cache) as client, self.assertRaises(Invalid):
            self.issue(client)
        self.sign.assert_not_called()

    def test_missing_policy_never_reaches_signer(self):
        del self.remote.targets[self.target]
        self.remote.publish()
        with self.remote.client(self.cache) as client, self.assertRaises(Invalid):
            self.issue(client)
        self.sign.assert_not_called()

    def test_epoch_floor_failure_never_reaches_signer(self):
        with self.remote.client(self.cache) as client, self.assertRaises(Invalid):
            self.issue(client, minimum_security_epoch=8)
        self.sign.assert_not_called()

    def test_invalid_lifetime_and_key_are_rejected_before_fetch(self):
        with self.remote.client(self.cache) as client:
            before = len(self.remote.requests)
            for value in (0, True, 3601):
                with self.subTest(lifetime=value), self.assertRaises(Invalid):
                    self.issue(client, maximum_lifetime_seconds=value)
            for value in (None, bytes(31), bytes(32), bytes(33)):
                with self.subTest(key=value), self.assertRaises(Invalid):
                    self.issue(client, public_key=value)
            self.assertEqual(len(self.remote.requests), before)
        self.sign.assert_not_called()

    def test_other_signer_or_domain_cannot_issue(self):
        other = Ed25519PrivateKey.generate()
        for signer in (other.sign, lambda message: self.key.sign(message[2:])):
            with self.remote.client(self.cache) as client, self.assertRaisesRegex(Invalid, 'independent key'):
                self.issue(client, sign=signer)

    def test_signature_length_and_type_are_checked(self):
        for signature in (None, bytes(63), bytes(65), bytearray(64)):
            with self.subTest(signature=signature), self.remote.client(self.cache) as client, self.assertRaises(Invalid):
                self.issue(client, sign=lambda message: signature)

    def test_signer_failure_is_not_an_issued_receipt(self):
        with self.remote.client(self.cache) as client, self.assertRaises(OSError):
            self.issue(client, sign=Mock(side_effect=OSError('provider unavailable')))

    def test_provider_cannot_change_retained_checkpoint(self):
        def signer(message):
            checkpoint = self.cache/'checkpoint.json'
            checkpoint.write_bytes(checkpoint.read_bytes()+b'\n')
            return self.key.sign(message)
        with self.remote.client(self.cache) as client, self.assertRaisesRegex(Invalid, 'checkpoint changed'):
            self.issue(client, sign=signer)

    def test_expiry_or_backward_clock_during_signing_is_rejected(self):
        for value in (self.fixture.now-1, self.fixture.now+3600):
            clock = SimpleNamespace(monotonic=time.monotonic, time=lambda: value)
            with self.remote.client(self.cache) as client, patch('archive_receipt.time', clock):
                with self.assertRaisesRegex(Invalid, 'during signing'):
                    self.issue(client)

    def test_total_issuance_deadline_is_finite(self):
        clock = SimpleNamespace(time=time.time, monotonic=Mock(side_effect=[100, 220]))
        with self.remote.client(self.cache) as client, patch('archive_receipt.time', clock):
            with self.assertRaisesRegex(Invalid, 'during signing'):
                self.issue(client)

    def test_tuf_metadata_deadline_caps_receipt(self):
        expiry = datetime.now(timezone.utc)+timedelta(seconds=120)
        self.remote.role_expiries['timestamp'] = expiry
        self.remote.publish()
        with self.remote.client(self.cache) as client:
            receipt = self.issue(client)
        self.assertEqual(struct.unpack('>Q', receipt.wire[248:256])[0], int(expiry.timestamp()))

    def test_root_is_rejected_before_any_supply_or_signer(self):
        with patch('archive_receipt.os.geteuid', return_value=0), self.assertRaisesRegex(Invalid, 'unprivileged'):
            issue(None, None, None, None, None, None, minimum_security_epoch=7,
                  maximum_lifetime_seconds=300, public_key=self.public_key, sign=self.sign)
        self.sign.assert_not_called()


if __name__ == '__main__':
    unittest.main()
