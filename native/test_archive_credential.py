# SPDX-License-Identifier: BSD-3-Clause
"""Bounded credential delivery with real archive authentication and Ed25519."""
import ctypes
import fcntl
import os
from pathlib import Path
import resource
import stat
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption

import test_archive_receipt as fixtures
import archive_credential as provider
from archive_receipt import scope, DOMAIN
from nia_common import Invalid


def credential(seed, *, mode=0o400, sealed=True, readonly=True):
    """Test-only ephemeral key transport; no production default or key files."""
    fd = os.memfd_create('nia-test-credential', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        os.write(fd, seed)
        os.fchmod(fd, mode)
        if sealed:
            fcntl.fcntl(fd, fcntl.F_ADD_SEALS, provider._SEALS)
        if readonly:
            result = os.open('/proc/self/fd/'+str(fd), os.O_RDONLY | os.O_CLOEXEC)
        else:
            result = os.dup(fd)
        return result
    finally:
        os.close(fd)


class CredentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ReceiptTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        fixtures.ReceiptTests.tearDownClass()

    def setUp(self):
        self.case = fixtures.ReceiptTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.seed = self.case.key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        self.fd = credential(self.seed)
        self.addCleanup(os.close, self.fd)

    def issue(self, repository, **kwargs):
        case = self.case
        args = dict(credential_fd=self.fd, expected_scope=scope(repository, case.target),
                    public_key=case.public_key, minimum_security_epoch=7,
                    maximum_lifetime_seconds=300)
        args.update(kwargs)
        return provider.issue_from_credential(repository, case.target, case.fixture.root,
                    case.fixture.fixture.keyring, case.fixture.index, case.fixture.path, **args)

    def test_authentication_to_credential_signature_preserves_borrowed_fd(self):
        os.lseek(self.fd, 17, os.SEEK_SET)
        with self.case.remote.client(self.case.cache) as repository:
            receipt = self.issue(repository)
        self.assertEqual(len(receipt.wire), 320)
        self.assertEqual(receipt.policy_bytes, self.case.policy)
        self.case.key.public_key().verify(receipt.wire[256:],
                struct.pack('>H', len(DOMAIN))+DOMAIN+receipt.wire[:256])
        self.assertEqual(os.lseek(self.fd, 0, os.SEEK_CUR), 17)
        self.assertEqual(resource.getrlimit(resource.RLIMIT_CORE), (0, 0))
        self.assertEqual(ctypes.CDLL(None).prctl(3, 0, 0, 0, 0), 0)

    def test_unauthenticated_original_never_reads_credential(self):
        (self.case.fixture.root/self.case.fixture.path).write_bytes(b'changed')
        original_pread = os.pread
        with self.case.remote.client(self.case.cache) as repository:
            with patch('archive_credential.os.pread', wraps=original_pread) as read:
                with self.assertRaises(Invalid):
                    self.issue(repository)
                read.assert_not_called()

    def test_scope_mismatch_and_bad_pins_precede_key_read_and_fetch(self):
        with self.case.remote.client(self.case.cache) as repository:
            before = len(self.case.remote.requests)
            invalid = [dict(expected_scope='a'*64), dict(expected_scope='0'*64),
                       dict(public_key=bytes(32)), dict(public_key=bytearray(32)),
                       dict(minimum_security_epoch=True), dict(maximum_lifetime_seconds=3601),
                       dict(credential_fd=True), dict(credential_fd=-1)]
            with patch('archive_credential.os.pread') as read:
                for arguments in invalid:
                    with self.subTest(fields=list(arguments)), self.assertRaises(Invalid):
                        self.issue(repository, **arguments)
                read.assert_not_called()
            self.assertEqual(len(self.case.remote.requests), before)

    def test_valid_but_different_key_is_refused_without_disclosure(self):
        other = Ed25519PrivateKey.generate().private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        fd = credential(other)
        try:
            with self.case.remote.client(self.case.cache) as repository:
                with self.assertRaisesRegex(Invalid, 'differs from independent key') as caught:
                    self.issue(repository, credential_fd=fd)
            self.assertNotIn(other.hex(), str(caught.exception))
        finally:
            os.close(fd)

    def test_nonimmutable_or_nonprivate_credentials_are_refused(self):
        cases = [(self.seed, {'sealed': False}), (self.seed, {'readonly': False}),
                 (self.seed, {'mode': 0o440}), (self.seed, {'mode': 0o600}),
                 (self.seed[:31], {}), (self.seed+b'x', {})]
        with self.case.remote.client(self.case.cache) as repository:
            for seed, options in cases:
                fd = credential(seed, **options)
                try:
                    with self.subTest(size=len(seed), options=options), self.assertRaises(Invalid):
                        self.issue(repository, credential_fd=fd)
                finally:
                    os.close(fd)

    def test_ordinary_readonly_file_on_writable_storage_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'credential'
            path.write_bytes(self.seed)
            path.chmod(0o400)
            fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
            try:
                with self.case.remote.client(self.case.cache) as repository:
                    with self.assertRaisesRegex(Invalid, 'mutable'):
                        self.issue(repository, credential_fd=fd)
            finally:
                os.close(fd)

    def test_service_acl_rejects_broader_read_access(self):
        # Captured systemd credential layout; UID is replaced with this test
        # process. VM acceptance separately exercises the actual kernel ACL.
        raw = bytes.fromhex('0200000001000400ffffffff02000400e7030000'
                            '04000000ffffffff10000400ffffffff20000000ffffffff')
        raw = raw[:16]+struct.pack('<I', os.geteuid())+raw[20:]
        original = os.fstat(self.fd)
        info = SimpleNamespace(**{name: getattr(original, name) for name in (
            'st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')},
            st_mode=stat.S_IFREG | 0o440, st_uid=0, st_gid=0, st_nlink=1)
        with patch('archive_credential.os.fstat', return_value=info), \
             patch('archive_credential.os.fstatvfs', return_value=SimpleNamespace(f_flag=os.ST_RDONLY)):
            with patch('archive_credential.os.getxattr', return_value=raw):
                provider._metadata(self.fd)
            bad = [raw[:16]+struct.pack('<I', os.geteuid()+1)+raw[20:],
                   raw[:22]+b'\x04\x00'+raw[24:],  # group owner can read
                   raw[:38]+b'\x04\x00'+raw[40:],  # everyone can read
                   raw+raw[12:20]]                 # extra named user entry
            for acl in bad:
                with self.subTest(acl_size=len(acl)):
                    with patch('archive_credential.os.getxattr', return_value=acl), self.assertRaises(Invalid):
                        provider._metadata(self.fd)
            with patch('archive_credential.os.getxattr', side_effect=OSError('missing')), self.assertRaises(Invalid):
                provider._metadata(self.fd)

    def test_missing_or_wrong_kind_fd_fails_without_blocking(self):
        reader, writer = os.pipe2(os.O_CLOEXEC)
        try:
            with self.case.remote.client(self.case.cache) as repository:
                with self.assertRaises(Invalid):
                    self.issue(repository, credential_fd=reader)
        finally:
            os.close(reader)
            os.close(writer)
        with self.case.remote.client(self.case.cache) as repository, self.assertRaises(OSError):
            self.issue(repository, credential_fd=2**30)

    def test_descriptor_duplicate_is_closed_on_authentication_failure(self):
        (self.case.fixture.root/self.case.fixture.path).write_bytes(b'changed')
        with self.case.remote.client(self.case.cache) as repository:
            before = set(os.listdir('/proc/self/fd'))
            with self.assertRaises(Invalid):
                self.issue(repository)
            self.assertEqual(set(os.listdir('/proc/self/fd')), before)

    def test_root_refusal_precedes_any_process_or_key_access(self):
        with patch('archive_credential.os.geteuid', return_value=0):
            with patch('archive_credential._protect_process') as protect:
                with self.assertRaisesRegex(Invalid, 'unprivileged'):
                    provider.issue_from_credential(None, None, None, None, None, None,
                        credential_fd=self.fd, expected_scope='a'*64, public_key=self.case.public_key,
                        minimum_security_epoch=7, maximum_lifetime_seconds=300)
                protect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
