# SPDX-License-Identifier: BSD-3-Clause
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from interim_package import (MAGIC, MAX_MANIFEST, MAX_ARTIFACT, Invalid,
                             encode, decode, build_file, inspect_file, check_manifest)
from nia_common import canonical, sha
from test_update_metadata import deb_fixture


def fixture():
    base = deb_fixture()
    target = deb_fixture({'version': '1:2.0-4', 'source': 'sample-src (1:2.0-4)'}, b'fixed payload')
    manifest = {
        'schema': 'org.niaos.interim-package/v1', 'label': 'fix001',
        'description': 'Synthetic interim fixture', 'release': 'trixie', 'architecture': 'amd64',
        'created_at': 100, 'expires_at': 200, 'security_epoch': 1,
        'advisories': ['NIA-TEST-001'], 'requires': [], 'conflicts': [], 'supersedes': [],
        'rollback_contract_sha256': sha(b'rollback contract reference, not authenticated'),
        'replacements': [{
            'base': {'package': 'sample-bin', 'version': '1:2.0-3+b1', 'architecture': 'amd64',
                     'artifact_sha256': sha(base), 'source_manifest_sha256': sha(b'base source reference')},
            'target': {'package': 'sample-bin', 'version': '1:2.0-4', 'architecture': 'amd64',
                       'artifact_sha256': sha(target), 'source_manifest_sha256': sha(b'target source reference')},
            'effect_contract_sha256': sha(b'effect contract reference, not authenticated'),
            'activation': 'service-restart'}]}
    return manifest, {sha(base): base, sha(target): target}


class InterimPackageTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.artifacts = fixture()

    def test_reproducible_roundtrip_preserves_original_debs(self):
        raw = encode(self.manifest, self.artifacts)
        reordered = dict(reversed(list(self.manifest.items())))
        other = encode(reordered, dict(reversed(list(self.artifacts.items()))))
        self.assertEqual(raw, other)
        manifest, artifacts = decode(raw)
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(artifacts, self.artifacts)

    def test_framing_rejects_truncation_corruption_and_extra_data(self):
        raw = encode(self.manifest, self.artifacts)
        start = len(MAGIC) + 4 + len(canonical(self.manifest))
        for length in (0, len(MAGIC), len(MAGIC) + 3, start - 1, start,
                       start + 31, start + 39, start + 40, len(raw) - 1):
            with self.subTest(length=length), self.assertRaises(Invalid):
                decode(raw[:length])
        for bad in (b'X' + raw[1:], raw + b'\x00', raw[:-1] + b'X'):
            with self.assertRaises(Invalid):
                decode(bad)

    def test_length_bounds_before_payload_read(self):
        with self.assertRaises(Invalid):
            decode(MAGIC + struct.pack('>I', MAX_MANIFEST + 1))
        raw = encode(self.manifest, self.artifacts)
        start = len(MAGIC) + 4 + len(canonical(self.manifest))
        bad = raw[:start + 32] + struct.pack('>Q', MAX_ARTIFACT + 1) + raw[start + 40:]
        with self.assertRaises(Invalid):
            decode(bad)

    def test_only_canonical_manifest_encoding(self):
        raw = encode(self.manifest, self.artifacts)
        start = len(MAGIC) + 4 + len(canonical(self.manifest))
        header = json.dumps(self.manifest, indent=2).encode()
        with self.assertRaises(Invalid):
            decode(MAGIC + struct.pack('>I', len(header)) + header + raw[start:])

    def test_original_control_identity_is_checked(self):
        self.manifest['replacements'][0]['target']['version'] = '1:2.0-5'
        with self.assertRaisesRegex(Invalid, 'original DEB identity'):
            encode(self.manifest, self.artifacts)

    def test_unlisted_missing_and_tampered_artifacts(self):
        extra = dict(self.artifacts, **{sha(b'extra'): b'extra'})
        missing = dict(self.artifacts)
        missing.pop(next(iter(missing)))
        corrupt = dict(self.artifacts)
        key = next(iter(corrupt))
        corrupt[key] += b'x'
        for data in (extra, missing, corrupt):
            with self.assertRaises(Invalid):
                encode(self.manifest, data)

    def test_unknown_manifest_fields_never_become_authority(self):
        for key in ('execution_permit', 'publisher_authenticated', 'script'):
            bad = copy.deepcopy(self.manifest)
            bad[key] = True
            with self.subTest(key=key), self.assertRaises(Invalid):
                check_manifest(bad)

    def test_invalid_platform_times_and_advisory(self):
        for key, value in (('release', 'sid'), ('architecture', 'arm64'), ('created_at', True),
                           ('expires_at', 100), ('security_epoch', 0), ('advisories', []),
                           ('advisories', ['NIA-TEST-001', 'NIA-TEST-001']),
                           ('label', '../outside'), ('description', 'bad\ntext')):
            bad = copy.deepcopy(self.manifest)
            bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(Invalid):
                check_manifest(bad)

    def test_duplicate_identity_and_unchanged_replacement(self):
        bad = copy.deepcopy(self.manifest)
        bad['replacements'].append(copy.deepcopy(bad['replacements'][0]))
        with self.assertRaises(Invalid):
            check_manifest(bad)
        bad = copy.deepcopy(self.manifest)
        bad['replacements'][0]['target'] = copy.deepcopy(bad['replacements'][0]['base'])
        with self.assertRaises(Invalid):
            check_manifest(bad)

    def test_fix_dependency_cannot_also_be_superseded(self):
        self.manifest['requires'] = [sha(b'required fix')]
        self.manifest['supersedes'] = self.manifest['requires'][:]
        with self.assertRaises(Invalid):
            check_manifest(self.manifest)

    def test_build_output_and_inspection_are_not_installation_or_trust(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = root / 'control.json'
            control.write_bytes(canonical(self.manifest))
            for key, data in self.artifacts.items():
                (root / (key + '.deb')).write_bytes(data)
            output = root / 'fix.epkg'
            result = build_file(control, root, output)
            self.assertEqual(result, sha(output.read_bytes()))
            observation = inspect_file(output)
            self.assertEqual(observation['contained_debs'], 2)
            for key in ('publisher_authenticated', 'contracts_authenticated', 'current_base_checked', 'execution_permit'):
                self.assertFalse(observation[key])
            before = output.read_bytes()
            with self.assertRaises(OSError):
                build_file(control, root, output)
            self.assertEqual(output.read_bytes(), before)

    def test_build_refuses_symlink_inputs_and_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = root / 'control.json'
            control.write_bytes(canonical(self.manifest))
            for key, data in self.artifacts.items():
                (root / (key + '.deb')).write_bytes(data)
            link = root / 'link.json'
            link.symlink_to(control)
            with self.assertRaises((Invalid, OSError)):
                build_file(link, root, root / 'output.epkg')
            self.assertFalse((root / 'output.epkg').exists())
            (root / 'output.epkg').symlink_to(control)
            before = control.read_bytes()
            with self.assertRaises((Invalid, OSError)):
                build_file(control, root, root / 'output.epkg')
            self.assertEqual(control.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
