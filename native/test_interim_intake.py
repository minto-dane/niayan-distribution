# SPDX-License-Identifier: MIT
import copy
import os
from pathlib import Path
import tempfile
import time
import unittest

from interim_download import download, load_policy
from interim_intake import authenticate
from interim_package import encode, decode
from nia_common import Invalid, canonical, sha
from package_cli import UsageError, parse
from test_interim_package import fixture
from test_repository import SignedRepository


class InterimIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.cache = self.directory / 'cache'
        self.remote = SignedRepository()
        self.remote.provision(self.cache)
        self.manifest, self.debs = fixture()
        self.manifest.update(created_at=int(time.time())-60, expires_at=int(time.time())+300, security_epoch=4)
        self.target = 'fixes/fix001.epkg'
        for kind, raw in (('contracts/rollback', b'rollback contract reference, not authenticated'),
                          ('contracts/effects', b'effect contract reference, not authenticated'),
                          ('sources', b'base source reference'), ('sources', b'target source reference')):
            self.remote.targets[kind + '/' + sha(raw) + '.json'] = raw
        self.publish()
        self.policy = dict(schema='org.niaos.repository-policy/v1', cache=str(self.cache),
                           bootstrap_sha256=sha(self.remote.bootstrap),
                           metadata_url=self.remote.metadata_url, targets_url=self.remote.targets_url,
                           security_epoch=4)
        self.policy_file = self.directory / 'repository.json'
        self.policy_file.write_bytes(canonical(self.policy))

    def publish(self):
        self.raw = encode(self.manifest, self.debs)
        self.remote.delegated[self.target] = self.raw
        self.remote.publish()

    def test_exact_artifact_and_references_use_real_delegated_signatures(self):
        with self.remote.client(self.cache) as client:
            result = authenticate(client, self.target, minimum_security_epoch=4)
        self.assertEqual(result.artifact, self.raw)
        self.assertEqual(decode(result.artifact)[1], self.debs)
        self.assertEqual(len(result.references), 4)
        observation = result.observation()
        self.assertTrue(observation['repository_authenticated'])
        self.assertTrue(observation['references_authenticated'])
        for key in ('execution_permit', 'current_base_checked', 'contract_semantics_checked', 'debian_archive_authenticated'):
            self.assertFalse(observation[key])

    def test_expired_and_future_artifacts_rejected_even_when_signed(self):
        for key, value in (('expires_at', int(time.time())-1), ('created_at', int(time.time())+60)):
            original = copy.deepcopy(self.manifest)
            self.manifest[key] = value
            self.publish()
            with self.remote.client(self.cache) as client:
                with self.assertRaises(Invalid):
                    authenticate(client, self.target, minimum_security_epoch=4)
            self.manifest = original
            self.remote.version += 1

    def test_independent_security_epoch_floor(self):
        with self.remote.client(self.cache) as client:
            with self.assertRaises(Invalid):
                authenticate(client, self.target, minimum_security_epoch=5)

    def test_outer_signature_cannot_supply_missing_reference(self):
        name = next(p for p in self.remote.targets if p.startswith('sources/'))
        del self.remote.targets[name]
        self.remote.publish()
        with self.remote.client(self.cache) as client:
            with self.assertRaises(Invalid):
                authenticate(client, self.target, minimum_security_epoch=4)

    def test_resigned_reference_with_different_hash_is_rejected(self):
        name = next(p for p in self.remote.targets if p.startswith('contracts/effects/'))
        self.remote.targets[name] = b'changed contract, correctly signed by its publisher'
        self.remote.publish()
        with self.remote.client(self.cache) as client:
            with self.assertRaisesRegex(Invalid, 'reference differs'):
                authenticate(client, self.target, minimum_security_epoch=4)

    def test_real_download_retains_exact_bytes_and_does_not_overwrite(self):
        output = self.directory / 'download'
        path = download(self.policy, self.remote.targets_url+self.target, output,
                        fetcher=self.remote, recheck=lambda: load_policy(self.policy_file, owner=os.geteuid()))
        self.assertEqual(path.read_bytes(), self.raw)
        self.assertEqual(list(output.iterdir()), [path])
        with self.assertRaises(FileExistsError):
            download(self.policy, self.remote.targets_url+self.target, output,
                     fetcher=self.remote, recheck=lambda: self.policy)
        self.assertEqual(path.read_bytes(), self.raw)

    def test_policy_change_prevents_output_publication(self):
        newer = dict(self.policy, security_epoch=5)
        output = self.directory / 'download'
        with self.assertRaisesRegex(Invalid, 'policy changed'):
            download(self.policy, self.remote.targets_url+self.target, output,
                     fetcher=self.remote, recheck=lambda: newer)
        self.assertFalse(output.exists())

    def test_policy_input_mutation_cannot_change_the_original_binding(self):
        output = self.directory / 'download'
        def changed():
            self.policy['security_epoch'] = 5
            return self.policy
        with self.assertRaisesRegex(Invalid, 'policy changed'):
            download(self.policy, self.remote.targets_url+self.target, output,
                     fetcher=self.remote, recheck=changed)
        self.assertFalse(output.exists())

    def test_failed_authentication_never_creates_output(self):
        self.manifest['expires_at'] = int(time.time())-1
        self.publish()
        output = self.directory / 'download'
        with self.assertRaises(Invalid):
            download(self.policy, self.remote.targets_url+self.target, output,
                     fetcher=self.remote, recheck=lambda: self.policy)
        self.assertFalse(output.exists())

    def test_untrusted_policy_owner_permissions_and_links_are_rejected(self):
        self.assertEqual(load_policy(self.policy_file, owner=os.geteuid()), self.policy)
        with self.assertRaises(Invalid):
            load_policy(self.policy_file, owner=os.geteuid()+1)
        self.policy_file.chmod(0o666)
        with self.assertRaises(Invalid):
            load_policy(self.policy_file, owner=os.geteuid())
        self.policy_file.chmod(0o600)
        link = self.directory / 'link.json'
        link.symlink_to(self.policy_file)
        with self.assertRaises(OSError):
            load_policy(link, owner=os.geteuid())
        link.unlink()
        os.link(self.policy_file, link)
        with self.assertRaises(Invalid):
            load_policy(self.policy_file, owner=os.geteuid())

    def test_foreign_download_url_and_invalid_syntax(self):
        for url in ('https://other.test/fix.epkg', self.remote.targets_url+'../fix.epkg',
                    self.remote.targets_url+'fixes/fix.epkg?skip=true', self.remote.targets_url+'fixes/fix.tar'):
            with self.subTest(url=url), self.assertRaises(Invalid):
                download(self.policy, url, self.directory/'output', fetcher=self.remote, recheck=lambda:self.policy)
        request = parse('emgr_download_ifix', ['-L', self.remote.targets_url+self.target, '-P', '/tmp/fixes'])
        self.assertEqual(request.action, 'interim-download')
        for args in ([], ['-P', '/tmp'], ['-L', 'one', '-L', 'two'], ['-L', 'one', 'operand']):
            with self.subTest(args=args), self.assertRaises(UsageError):
                parse('emgr_download_ifix', args)


if __name__ == '__main__':
    unittest.main()
