# SPDX-License-Identifier: MIT
"""Real TUF metadata signatures and cache lifecycle; no production signing keys."""
import copy
from datetime import datetime, timedelta, timezone
import os
import stat
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from securesystemslib.signer import CryptoSigner
from tuf.api import exceptions as tuf_errors
from tuf.api.metadata import (Metadata, Root, Timestamp, Snapshot, Targets,
                              TargetFile, MetaFile, Delegations, DelegatedRole)
from tuf.ngclient.fetcher import FetcherInterface

from repository import Repository, HTTPSFetcher, Invalid, initialize, sha, base_url, target_path, decode_checkpoint, HTTPError


class SignedRepository(FetcherInterface):
    metadata_url = 'https://supply.example.test/metadata/'
    targets_url = 'https://supply.example.test/targets/'

    def __init__(self):
        self.keys = {name: CryptoSigner.generate_ed25519() for name in ('root', 'timestamp', 'snapshot', 'targets', 'fixes')}
        self.expires = datetime.now(timezone.utc) + timedelta(days=1)
        self.root = Metadata(Root(expires=self.expires))
        for name in ('root', 'timestamp', 'snapshot', 'targets'):
            self.root.signed.add_key(self.keys[name].public_key, name)
        self.root.sign(self.keys['root'])
        self.bootstrap = self.root.to_bytes()
        self.files = {}
        self.requests = []
        self.targets = {'packages/sample.deb': b'opaque ordinary artifact fixture'}
        self.delegated = {}
        self.delegation_pattern = 'fixes/*'
        self.version = 1
        self.publish()

    def _fetch(self, url):
        self.requests.append(url)
        if url not in self.files:
            raise tuf_errors.DownloadHTTPError('fixture missing', 404)
        yield self.files[url]

    def publish(self):
        targets = Metadata(Targets(version=self.version, expires=self.expires))
        for name, data in self.targets.items():
            targets.signed.targets[name] = TargetFile.from_data(name, data, ['sha256'])
        roles = {}
        if self.delegated:
            key = self.keys['fixes'].public_key
            targets.signed.delegations = Delegations({key.keyid: key},
                {'fixes': DelegatedRole('fixes', [key.keyid], 1, True, paths=[self.delegation_pattern])})
            fixes = Metadata(Targets(version=self.version, expires=self.expires))
            for name, data in self.delegated.items():
                fixes.signed.targets[name] = TargetFile.from_data(name, data, ['sha256'])
            fixes.sign(self.keys['fixes'])
            roles['fixes'] = fixes.to_bytes()
        targets.sign(self.keys['targets'])
        roles['targets'] = targets.to_bytes()
        snapshot = Metadata(Snapshot(version=self.version, expires=self.expires))
        for name, data in roles.items():
            snapshot.signed.meta[name + '.json'] = MetaFile.from_data(self.version, data, ['sha256'])
        snapshot.sign(self.keys['snapshot'])
        raw_snapshot = snapshot.to_bytes()
        timestamp = Metadata(Timestamp(version=self.version, expires=self.expires,
            snapshot_meta=MetaFile.from_data(self.version, raw_snapshot, ['sha256'])))
        timestamp.sign(self.keys['timestamp'])
        self.files[self.metadata_url + 'timestamp.json'] = timestamp.to_bytes()
        self.files[self.metadata_url + str(self.version) + '.snapshot.json'] = raw_snapshot
        for name, data in roles.items():
            self.files[self.metadata_url + str(self.version) + '.' + name + '.json'] = data
        for path, data in (self.targets | self.delegated).items():
            directory, _, name = path.rpartition('/')
            self.files[self.targets_url + directory + '/' + sha(data) + '.' + name] = data

    def client(self, cache):
        return Repository(cache, sha(self.bootstrap), self.metadata_url, self.targets_url, fetcher=self)

    def provision(self, cache):
        initialize(cache, self.bootstrap, sha(self.bootstrap), self.metadata_url, self.targets_url)


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.cache = Path(self.temporary.name) / 'cache'
        self.remote = SignedRepository()
        self.remote.provision(self.cache)

    def test_real_chain_target_hash_and_cache_reopen(self):
        for _ in range(2):
            with self.remote.client(self.cache) as client:
                self.assertEqual(client.target('packages/sample.deb'), self.remote.targets['packages/sample.deb'])
        self.assertIn('timestamp.json', decode_checkpoint((self.cache / 'checkpoint.json').read_bytes()))
        self.assertEqual(os.stat(self.cache).st_mode & 0o777, 0o700)

    def test_delegated_publisher_cannot_publish_outside_scope(self):
        self.remote.delegated = {'fixes/fix.epkg': b'fix fixture', 'packages/escape.deb': b'not delegated'}
        self.remote.publish()
        with self.remote.client(self.cache) as client:
            self.assertEqual(client.target('fixes/fix.epkg'), b'fix fixture')
            with self.assertRaises(Invalid):
                client.target('packages/escape.deb')

    def test_download_corruption_and_session_poisoning(self):
        url = next(u for u in self.remote.files if u.startswith(self.remote.targets_url))
        self.remote.files[url] = b'modified target'
        with self.remote.client(self.cache) as client:
            with self.assertRaises(tuf_errors.RepositoryError):
                client.target('packages/sample.deb')
            with self.assertRaises(Invalid):
                client.target('packages/sample.deb')

    def test_wrong_signature_and_mixed_snapshot_rejected(self):
        original = dict(self.remote.files)
        for bad in (b'broken metadata', Metadata(Targets(expires=self.remote.expires)).to_bytes()):
            self.remote.files[self.remote.metadata_url + '1.targets.json'] = bad
            with self.assertRaises(tuf_errors.RepositoryError):
                with self.remote.client(self.cache):
                    pass
            self.remote.files = dict(original)

    def test_expired_signed_metadata_is_rejected(self):
        self.remote.expires = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.remote.publish()
        with self.assertRaises(tuf_errors.ExpiredMetadataError):
            with self.remote.client(self.cache):
                pass

    def test_persisted_timestamp_rejects_rollback_on_next_process_context(self):
        older = dict(self.remote.files)
        self.remote.version = 2
        self.remote.publish()
        with self.remote.client(self.cache) as client:
            client.target('packages/sample.deb')
        self.remote.files = older
        with self.assertRaises(tuf_errors.BadVersionNumberError):
            with self.remote.client(self.cache):
                pass

    def test_root_rotation_requires_old_and_new_root_signatures(self):
        new = CryptoSigner.generate_ed25519()
        rotated = copy.deepcopy(self.remote.root)
        rotated.signed.version = 2
        old_key = self.remote.keys['root'].public_key.keyid
        rotated.signed.revoke_key(old_key, 'root')
        rotated.signed.add_key(new.public_key, 'root')
        rotated.sign(new)
        self.remote.files[self.remote.metadata_url + '2.root.json'] = rotated.to_bytes()
        with self.assertRaises(tuf_errors.UnsignedMetadataError):
            with self.remote.client(self.cache):
                pass
        rotated.sign(self.remote.keys['root'], append=True)
        self.remote.files[self.remote.metadata_url + '2.root.json'] = rotated.to_bytes()
        with self.remote.client(self.cache) as client:
            client.target('packages/sample.deb')
        saved = decode_checkpoint((self.cache / 'checkpoint.json').read_bytes())
        self.assertEqual(Metadata.from_bytes(saved['root.json']).signed.version, 2)
        with self.remote.client(self.cache) as client:
            client.target('packages/sample.deb')

    def test_rotated_root_revokes_old_target_publisher(self):
        rotated = copy.deepcopy(self.remote.root)
        rotated.signed.version = 2
        rotated.signed.revoke_key(self.remote.keys['targets'].public_key.keyid, 'targets')
        rotated.signed.add_key(CryptoSigner.generate_ed25519().public_key, 'targets')
        rotated.sign(self.remote.keys['root'])
        self.remote.files[self.remote.metadata_url + '2.root.json'] = rotated.to_bytes()
        with self.assertRaises(tuf_errors.UnsignedMetadataError):
            with self.remote.client(self.cache):
                pass

    def test_cache_lock_is_exclusive_and_released_on_failure(self):
        with self.remote.client(self.cache):
            with self.assertRaises(BlockingIOError):
                with self.remote.client(self.cache):
                    pass
        with self.remote.client(self.cache):
            pass

    def test_missing_cache_is_never_automatically_reset(self):
        (self.cache / 'checkpoint.json').unlink()
        before = set(self.cache.iterdir())
        with self.assertRaises(OSError):
            with self.remote.client(self.cache):
                pass
        self.assertEqual(set(self.cache.iterdir()), before)
        with self.assertRaises(FileExistsError):
            self.remote.provision(self.cache)

    def test_cache_binding_permissions_links_and_lock_replacement(self):
        with self.assertRaises(Invalid):
            with Repository(self.cache, sha(b'different pin'), self.remote.metadata_url,
                            self.remote.targets_url, fetcher=self.remote):
                pass
        self.cache.chmod(0o777)
        with self.assertRaises(Invalid):
            with self.remote.client(self.cache):
                pass
        self.cache.chmod(0o700)
        link = self.cache / 'linked.json'
        link.symlink_to(self.cache / 'checkpoint.json')
        with self.assertRaises((Invalid, OSError)):
            with self.remote.client(self.cache):
                pass
        link.unlink()
        with self.remote.client(self.cache) as client:
            (self.cache / 'writer.lock').unlink()
            (self.cache / 'writer.lock').touch(mode=0o600)
            with self.assertRaisesRegex(Invalid, 'reservation changed'):
                client.target('packages/sample.deb')

    def test_target_limit_checked_before_payload_download(self):
        with self.remote.client(self.cache) as client:
            self.remote.requests.clear()
            with self.assertRaises(Invalid):
                client.target('packages/sample.deb', 1)
            self.assertFalse(any(u.startswith(self.remote.targets_url) for u in self.remote.requests))

    def test_independent_bootstrap_pin_and_root_threshold(self):
        other = self.cache.parent / 'other'
        with self.assertRaises(Invalid):
            initialize(other, self.remote.bootstrap, sha(b'not this root'), self.remote.metadata_url, self.remote.targets_url)
        self.assertFalse(other.exists())
        unsigned = Metadata(Root(expires=self.remote.expires)).to_bytes()
        with self.assertRaises((tuf_errors.RepositoryError, ValueError)):
            initialize(other, unsigned, sha(unsigned), self.remote.metadata_url, self.remote.targets_url)
        self.assertFalse(other.exists())

    def test_sync_failure_never_returns_authenticated_target(self):
        self.remote.delegated = {'fixes/new.epkg': b'fixture'}
        self.remote.publish()
        with self.remote.client(self.cache) as client:
            with patch('repository.os.fsync', side_effect=OSError('synthetic sync failure')):
                with self.assertRaises(OSError):
                    client.target('fixes/new.epkg')
            with self.assertRaises(Invalid):
                client.target('packages/sample.deb')

    def test_interrupted_refresh_retains_complete_previous_checkpoint(self):
        with self.remote.client(self.cache):
            pass
        before = (self.cache / 'checkpoint.json').read_bytes()
        self.remote.version = 2
        self.remote.publish()
        real_replace = os.replace
        def fail_checkpoint(source, destination, *args, **kwargs):
            if destination == 'checkpoint.json':
                raise OSError('before checkpoint publication')
            return real_replace(source, destination, *args, **kwargs)
        with patch('repository.os.replace', side_effect=fail_checkpoint):
            with self.assertRaises(OSError):
                with self.remote.client(self.cache):
                    pass
        self.assertEqual((self.cache / 'checkpoint.json').read_bytes(), before)
        self.assertEqual(len(list(self.cache.iterdir())), 3)
        with self.remote.client(self.cache):
            pass
        after = decode_checkpoint((self.cache / 'checkpoint.json').read_bytes())
        self.assertEqual(Metadata.from_bytes(after['timestamp.json']).signed.version, 2)

    def test_sync_failure_after_replace_leaves_a_complete_new_checkpoint(self):
        with self.remote.client(self.cache):
            pass
        self.remote.version = 2
        self.remote.publish()
        inode = os.stat(self.cache).st_ino
        real_sync = os.fsync
        def fail_directory(fd):
            info = os.fstat(fd)
            if stat.S_ISDIR(info.st_mode) and info.st_ino == inode:
                raise OSError('after checkpoint replace')
            real_sync(fd)
        with patch('repository.os.fsync', side_effect=fail_directory):
            with self.assertRaises(OSError):
                with self.remote.client(self.cache):
                    pass
        metadata = decode_checkpoint((self.cache / 'checkpoint.json').read_bytes())
        self.assertEqual(Metadata.from_bytes(metadata['timestamp.json']).signed.version, 2)
        with self.remote.client(self.cache):
            pass

    def test_stream_transport_errors_are_normalized(self):
        fetcher = HTTPSFetcher(self.remote.metadata_url, self.remote.targets_url)
        self.addCleanup(fetcher.close)
        def broken_stream(_):
            yield b'partial response'
            raise HTTPError('synthetic midstream failure')
        with patch.object(fetcher, '_stream', broken_stream):
            with self.assertRaises(tuf_errors.DownloadError):
                list(fetcher.fetch(self.remote.metadata_url+'timestamp.json'))

    def test_partial_temporary_checkpoint_is_discarded_under_lock(self):
        partial = self.cache / ('.cache-tmp-' + '1'*32)
        partial.write_bytes(b'interrupted write')
        partial.chmod(0o600)
        with self.remote.client(self.cache) as client:
            client.target('packages/sample.deb')
        self.assertFalse(partial.exists())

    def test_corrupt_checkpoint_is_not_reset_to_bootstrap(self):
        checkpoint = self.cache / 'checkpoint.json'
        checkpoint.write_bytes(b'{"schema":"wrong","metadata":{}}')
        before = checkpoint.read_bytes()
        with self.assertRaises(Invalid):
            with self.remote.client(self.cache):
                pass
        self.assertEqual(checkpoint.read_bytes(), before)
        self.assertEqual(self.remote.requests, [])

    def test_network_urls_are_not_inferred_from_untrusted_names(self):
        for url in ('http://supply.test/', 'https://user:secret@supply.test/',
                    'https://supply.test/../other/', 'https://supply.test/%2f/',
                    'https://supply.test/?token=secret', 'https://supply.test:bad/'):
            with self.subTest(url=url), self.assertRaises((Invalid, ValueError)):
                base_url(url)
        for name in ('../root.json', '/root.json', 'a//b', 'a/%2e%2e/b', 'https://other.test/a'):
            with self.subTest(name=name), self.assertRaises(Invalid):
                target_path(name)
        fetcher = HTTPSFetcher(self.remote.metadata_url, self.remote.targets_url)
        self.addCleanup(fetcher.close)
        self.assertFalse(fetcher.session.trust_env)
        with patch.object(fetcher.session, 'get') as get:
            with self.assertRaises(tuf_errors.DownloadError):
                list(fetcher.fetch('https://other.example.test/secret'))
            get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
