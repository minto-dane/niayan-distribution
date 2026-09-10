# SPDX-License-Identifier: BSD-3-Clause
"""Real signatures and original DEBs for explicitly pinned Debian 13 supply."""
import copy
import email.utils
import lzma
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

import test_nia_intake as legacy
from debian_archive_auth import auth_policy, verify_release, verify_snapshot, verify_source, MAX_INDEX
from nia_common import Invalid, sha


class TrixieTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not all(shutil.which(tool) for tool in ('gpg', 'gpgv', 'gpgconf', 'gpg-agent', 'dpkg-deb')):
            raise RuntimeError('archive qualification requires GPG, agent, gpgv, gpgconf and dpkg-deb')
        legacy.NativeFixture.setUpClass()

    @classmethod
    def tearDownClass(cls):
        legacy.NativeFixture.tearDownClass()

    def setUp(self):
        self.fixture = legacy.NativeFixture()
        self.fixture.setUp()
        self.root = self.fixture.snapshot
        self.now = self.fixture.now
        self.index = self.fixture.index
        self.path = self.fixture.path
        for pocket in ('trixie', 'trixie-updates', 'trixie-security', 'trixie-backports'):
            directory = self.root / 'dists' / pocket
            if directory.exists():
                shutil.rmtree(directory)
        self.publish()

    def publish(self, *, codename='trixie', architecture='amd64', valid_until=False,
                overrides=None, extra=b'', packed=None):
        suffix = codename.removeprefix('trixie')
        self.index = f'main/binary-{architecture}/Packages.xz'
        base = dict(Origin='Debian', Label='Debian-Security' if suffix == '-security' else 'Debian',
                    Suite='stable'+suffix, Codename=codename,
                    Architectures=architecture+' all', Components='updates/main' if suffix == '-security' else 'main')
        base.update(overrides or {})
        release = self.fixture.make_release(**base)
        if not valid_until:
            release = b'\n'.join(line for line in release.split(b'\n') if not line.startswith(b'Valid-Until:'))
        content = self.fixture.packed if packed is None else packed
        old = f' {sha(self.fixture.packed)} {len(self.fixture.packed)} {self.fixture.index}\n'.encode()
        release = release.replace(old, f' {sha(content)} {len(content)} {self.index}\n'.encode()) + extra
        self.signed = self.fixture.sign(release)
        directory = self.root / 'dists' / codename
        (directory / self.index).parent.mkdir(parents=True, exist_ok=True)
        (directory / self.index).write_bytes(content)
        (directory / 'InRelease').write_bytes(self.signed)
        self.policy = {k: copy.deepcopy(v) for k, v in self.fixture.policy.items() if k != 'now'}
        self.policy.update(schema='org.niaos.debian-trust/v2', max_age_seconds=90*86400 if codename == 'trixie' else 86400,
                           release={'codename': codename, 'suite': 'stable'+suffix, 'architecture': architecture,
                                    'components': ['main'], 'inrelease_sha256': sha(self.signed),
                                    'minimum_date': self.now-90*86400, 'expires': self.now+1800})

    def verify(self, **kwargs):
        return verify_snapshot(self.root, self.fixture.keyring, self.policy, self.index, self.path,
                               now=kwargs.get('now', self.now))

    def test_pinned_stable_without_upstream_expiry(self):
        result = self.verify()
        self.assertEqual(result['codename'], 'trixie')
        self.assertEqual(result['valid_until'], self.now+1800)
        self.assertTrue(result['observation']['archive_authenticated'])
        self.assertFalse(result['execution_permit'])
        release = verify_release(self.root, self.fixture.keyring, self.policy, now=self.now)
        self.assertIsNone(release['upstream_valid_until'])
        self.assertFalse(release['artifacts_authenticated'])
        self.assertFalse((self.fixture.root/'SCRIPT_WAS_EXECUTED').exists())

    def test_each_update_pocket_requires_upstream_expiry(self):
        for pocket in ('trixie-updates', 'trixie-security', 'trixie-backports'):
            with self.subTest(pocket=pocket):
                self.publish(codename=pocket, valid_until=True)
                self.assertEqual(self.verify()['codename'], pocket)
                self.publish(codename=pocket)
                with self.assertRaisesRegex(Invalid, 'Valid-Until missing'):
                    self.verify()

    def test_policy_schema_is_closed_and_time_is_separate(self):
        for value in (None, {}, self.policy | {'now': self.now}, self.policy | {'skip_expiry': True}):
            with self.subTest(value=value), self.assertRaises(Invalid):
                auth_policy(value)
        for now in (None, True, 0, -1, 1.5):
            with self.subTest(now=now), self.assertRaises(Invalid):
                self.verify(now=now)

    def test_invalid_pinned_policy_fields(self):
        for field, value in [('codename', 'forky'), ('codename', '../trixie'), ('codename', []),
                             ('suite', 'testing'), ('suite', 'stable-security'),
                             ('architecture', 'all'), ('architecture', '../amd64'),
                             ('components', []), ('components', ['main', 'main']),
                             ('components', ['main', 'contrib']), ('components', ['unknown']),
                             ('inrelease_sha256', '0'*64), ('minimum_date', True),
                             ('expires', 0)]:
            policy = copy.deepcopy(self.policy)
            policy['release'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(Invalid):
                auth_policy(policy)

    def test_trusted_pin_cannot_be_replaced_by_another_valid_signature(self):
        alternate = self.fixture.sign(self.fixture.make_release(Codename='trixie', Suite='stable'))
        (self.root/'dists/trixie/InRelease').write_bytes(alternate)
        with self.assertRaisesRegex(Invalid, 'independent pin'):
            self.verify()

    def test_hash_pin_does_not_replace_signature(self):
        changed = self.signed.replace(b'Codename: trixie', b'Codename: forky')
        (self.root/'dists/trixie/InRelease').write_bytes(changed)
        self.policy['release']['inrelease_sha256'] = sha(changed)
        with self.assertRaisesRegex(Invalid, 'signature validation'):
            self.verify()

    def test_identity_and_scope_requirements(self):
        for overrides in ({'Origin': 'Other'}, {'Label': 'Other'}, {'Suite': 'oldstable'},
                          {'Codename': 'forky'}, {'Architectures': 'arm64 all'},
                          {'Architectures': 'amd64 amd64'}, {'Components': 'contrib'},
                          {'Components': 'main main'}):
            self.publish(overrides=overrides)
            with self.subTest(overrides=overrides), self.assertRaises(Invalid):
                self.verify()

    def test_pinned_oldstable_requires_explicit_policy_change(self):
        self.publish(overrides={'Suite': 'oldstable'})
        self.policy['release']['suite'] = 'oldstable'
        self.assertEqual(self.verify()['codename'], 'trixie')

    def test_security_component_prefix_is_not_a_general_alias(self):
        self.publish(codename='trixie-security', valid_until=True, overrides={'Components': 'main'})
        with self.assertRaisesRegex(Invalid, 'component policy'):
            self.verify()
        self.publish(overrides={'Components': 'updates/main'})
        with self.assertRaisesRegex(Invalid, 'component policy'):
            self.verify()

    def test_expiry_floor_future_and_age_boundaries(self):
        with self.assertRaises(Invalid):
            self.verify(now=self.now+1800)
        self.policy['release']['minimum_date'] = self.now
        with self.assertRaisesRegex(Invalid, 'date floor'):
            self.verify()
        self.publish(overrides={'Date': email.utils.formatdate(self.now+301, usegmt=True)})
        with self.assertRaisesRegex(Invalid, 'future'):
            self.verify()
        self.publish(overrides={'Date': email.utils.formatdate(self.now-40*86400, usegmt=True)})
        self.assertTrue(self.verify()['observation']['archive_authenticated'])
        self.policy['max_age_seconds'] = 40*86400
        with self.assertRaisesRegex(Invalid, 'stale'):
            self.verify()

    def test_present_upstream_expiry_is_never_ignored(self):
        for expiry in ('', email.utils.formatdate(self.now, usegmt=True)):
            self.publish(valid_until=True, overrides={'Valid-Until': expiry})
            with self.subTest(expiry=expiry), self.assertRaises(Invalid):
                self.verify()
        self.publish(valid_until=True, overrides={'Valid-Until': email.utils.formatdate(self.now+20, usegmt=True)})
        self.assertEqual(self.verify()['valid_until'], self.now+20)

    def test_unrelated_large_contents_is_not_read_or_allocated(self):
        self.publish(extra=f" {'a'*64} 911454163 main/Contents-source\n".encode())
        self.assertTrue(self.verify()['observation']['archive_authenticated'])

    def test_selected_large_index_is_rejected_before_read(self):
        original = self.fixture.packed
        release = self.fixture.make_release(Codename='trixie', Suite='stable').replace(
            f'{len(original)} {self.index}'.encode(), f'{MAX_INDEX+1} {self.index}'.encode())
        signed = self.fixture.sign(release)
        (self.root/'dists/trixie/InRelease').write_bytes(signed)
        self.policy['release']['inrelease_sha256'] = sha(signed)
        with self.assertRaisesRegex(Invalid, 'selected Packages byte limit'):
            self.verify()

    def test_control_architecture_follows_explicit_index_policy(self):
        control = self.fixture.root/'package/DEBIAN/control'
        original = control.read_bytes()
        try:
            control.write_bytes(original.replace(b'Architecture: all', b'Architecture: arm64'))
            target = self.fixture.root/'arm64.deb'
            subprocess.run(['dpkg-deb', '--build', '--root-owner-group', '-Zxz', str(control.parent.parent), str(target)],
                           check=True, capture_output=True)
            raw = target.read_bytes()
        finally:
            control.write_bytes(original)
        packages = self.fixture.packages.replace(b'Architecture: all', b'Architecture: arm64').replace(
            str(len(self.fixture.deb)).encode(), str(len(raw)).encode()).replace(sha(self.fixture.deb).encode(), sha(raw).encode())
        self.publish(architecture='arm64', packed=lzma.compress(packages))
        (self.root/self.path).write_bytes(raw)
        self.assertEqual(self.verify()['observation']['identity']['architecture'], 'arm64')
        self.publish(packed=lzma.compress(packages))
        with self.assertRaisesRegex(Invalid, 'package architecture'):
            self.verify()

    def test_source_uses_same_pinned_release_and_codename(self):
        source, _, _ = self.fixture.prepare_source()
        raw = (self.root/'dists/forky'/source).read_bytes()
        self.publish(extra=f' {sha(raw)} {len(raw)} {source}\n'.encode())
        target = self.root/'dists/trixie'/source
        target.parent.mkdir(parents=True)
        target.write_bytes(raw)
        result = verify_source(self.root, self.fixture.keyring, self.policy, self.index, self.path, source, now=self.now)
        self.assertEqual(result['source_manifest']['codename'], 'trixie')
        self.assertTrue(result['source_authenticated'])
        self.assertFalse(result['execution_permit'])
        target.write_bytes(raw+b'changed')
        with self.assertRaises(Invalid):
            verify_source(self.root, self.fixture.keyring, self.policy, self.index, self.path, source, now=self.now)


if __name__ == '__main__':
    unittest.main()
