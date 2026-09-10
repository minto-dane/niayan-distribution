# SPDX-License-Identifier: BSD-3-Clause
"""Protocol/configuration boundaries; real packaged service is checked in a VM."""
import array
import copy
import fcntl
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest

import archive_observer as service
from archive_receipt import scope
from nia_common import canonical, Invalid
from repository import Repository


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repository = Repository(self.root/'cache', 'a'*64, 'https://example.test/metadata/', 'https://example.test/targets/')
        self.scope = scope(self.repository, 'archives/trixie.json')
        self.config = dict(schema='org.niaos.archive-observer/v1', root_sha256='a'*64,
            metadata_url='https://example.test/metadata/', targets_url='https://example.test/targets/',
            public_key='b'*64, scopes=[dict(scope=self.scope, target='archives/trixie.json', codename='trixie',
                                          minimum_security_epoch=7, maximum_lifetime_seconds=300)])
        self.job = dict(schema='org.niaos.archive-observer-request/v1', request_id='c'*64, scope=self.scope,
                        index='main/binary-amd64/Packages.xz', deb='pool/test.deb')

    def test_configuration_binds_repository_target_and_site_limits(self):
        self.assertEqual(service.configuration(canonical(self.config)), self.config)
        for key, value in [('scope', 'd'*64), ('codename', 'other'), ('minimum_security_epoch', True),
                           ('maximum_lifetime_seconds', 3601), ('target', '../elsewhere')]:
            config = copy.deepcopy(self.config)
            config['scopes'][0][key] = value
            with self.subTest(field=key), self.assertRaises(Invalid):
                service.configuration(canonical(config))

    def test_duplicate_unknown_or_empty_configuration_is_refused(self):
        for config in [self.config | {'scopes': []}, self.config | {'scopes': self.config['scopes']*2},
                       self.config | {'private_key': 'unsupported'}, self.config | {'metadata_url': 'http://example.test/'}]:
            with self.assertRaises(Invalid):
                service.configuration(canonical(config))

    def test_request_identity_and_paths_are_canonical(self):
        self.assertEqual(service.request(canonical(self.job)), self.job)
        for key, value in [('request_id', '0'*64), ('scope', '0'*64), ('deb', '../escape'),
                           ('deb', '/absolute'), ('index', 'a/'*32+'b')]:
            with self.subTest(field=key), self.assertRaises(Invalid):
                service.request(canonical(self.job | {key: value}))
        with self.assertRaises(Invalid):
            service.request(canonical(self.job)+b'\n')
        with self.assertRaises(Invalid):
            service.request(canonical(self.job | {'sign': 'arbitrary'}))

    def test_private_copy_preserves_original_offset_and_refuses_overwrite(self):
        source = self.root/'input'; source.write_bytes(b'authenticated later')
        fd = os.open(source, os.O_RDONLY | os.O_CLOEXEC)
        try:
            os.lseek(fd, 7, os.SEEK_SET)
            target = self.root/'copy/original'
            service.copy_original(fd, target, 1024, time.monotonic()+5)
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(os.lseek(fd, 0, os.SEEK_CUR), 7)
            with self.assertRaises(FileExistsError):
                service.copy_original(fd, target, 1024, time.monotonic()+5)
            with self.assertRaises(Invalid):
                service.copy_original(fd, self.root/'expired', 1024, time.monotonic()-1)
        finally:
            os.close(fd)

    def test_writable_nonregular_empty_and_oversize_originals_are_refused(self):
        source = self.root/'input'; source.write_bytes(b'1234')
        for path, flags, limit in [(source, os.O_RDWR, 4), (source, os.O_RDONLY, 3),
                                  (self.root, os.O_RDONLY | os.O_DIRECTORY, 4096)]:
            fd = os.open(path, flags)
            try:
                with self.assertRaises(Invalid):
                    service.copy_original(fd, self.root/'copy', limit, time.monotonic()+5)
            finally:
                os.close(fd)
        source.write_bytes(b'')
        fd = os.open(source, os.O_RDONLY)
        try:
            with self.assertRaises(Invalid):
                service.copy_original(fd, self.root/'copy', 4096, time.monotonic()+5)
        finally:
            os.close(fd)

    def test_received_descriptors_are_closed_on_count_or_packet_failure(self):
        fd = service.sealed(b'fixture')
        try:
            for count, raw in [(2, b'{}'), (4, b'{}'), (3, b'x'*(service.MAX_PACKET+1))]:
                left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
                with left, right:
                    before = set(os.listdir('/proc/self/fd'))
                    left.sendmsg([raw], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [fd]*count))])
                    with self.assertRaises(Invalid):
                        service.receive(right, 3)
                    self.assertEqual(set(os.listdir('/proc/self/fd')), before)
        finally:
            os.close(fd)

    def test_received_descriptors_are_close_on_exec(self):
        fd = service.sealed(b'fixture')
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            with left, right:
                left.sendmsg([b'{}'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [fd]*3))])
                raw, descriptors = service.receive(right, 3)
                try:
                    self.assertEqual(raw, b'{}')
                    self.assertTrue(all(not os.get_inheritable(d) for d in descriptors))
                finally:
                    for descriptor in descriptors:
                        os.close(descriptor)
        finally:
            os.close(fd)

    def test_result_descriptors_are_fully_sealed_and_readonly(self):
        fd = service.sealed(b'receipt')
        try:
            self.assertEqual(os.pread(fd, 64, 0), b'receipt')
            self.assertEqual(fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE, os.O_RDONLY)
            self.assertEqual(fcntl.fcntl(fd, fcntl.F_GET_SEALS) & service.SEALS, service.SEALS)
            with self.assertRaises(OSError):
                os.write(fd, b'changed')
        finally:
            os.close(fd)

    def test_caller_owned_configuration_is_not_site_authority(self):
        path = self.root/'config'; path.write_bytes(canonical(self.config)); path.chmod(0o444)
        with self.assertRaises(Invalid):
            service.protected(path, service.MAX_CONFIG)


if __name__ == '__main__':
    unittest.main()
