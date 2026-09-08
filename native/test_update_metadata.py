# SPDX-License-Identifier: MIT
import io
import tarfile
import unittest

from update_metadata import Invalid, advisory_matches, inspect_update, source_identity, upload_metadata
from nia_common import sha


CONTROL = {'package': 'sample-bin', 'version': '1:2.0-3+b1',
           'source': 'sample-src (1:2.0-3)', 'architecture': 'amd64',
           'priority': 'required'}
DSA = b'''[08 Sep 2026] DSA-90000-1 sample-src - security update
\t{CVE-2026-90000 CVE-2026-90001}
\t[bookworm] - sample-src 1:1.0-1
\t[trixie] - sample-src 1:2.0-3
'''


def changes(urgency='emergency', artifact=b'test'):
    return (f'Format: 1.8\nSource: sample-src (1:2.0-3)\n'
            f'Binary: sample-bin\nArchitecture: amd64\nVersion: 1:2.0-3+b1\n'
            f'Distribution: trixie-security\nUrgency: {urgency}\n'
            f'Checksums-Sha256:\n {sha(artifact)} {len(artifact)} sample.deb\n').encode()


def deb_fixture(control_fields=None, payload=b'payload'):
    def tar(name, content):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode = len(content), 0o644
            archive.addfile(entry, io.BytesIO(content))
        return output.getvalue()
    control = dict(CONTROL, maintainer='Nia fixture', description='Synthetic test input')
    control.update(control_fields or {})
    members = [('debian-binary', b'2.0\n'),
               ('control.tar', tar('control', ''.join(f'{k}: {v}\n' for k, v in control.items()).encode())),
               ('data.tar', tar('sample', payload))]
    result = b'!<arch>\n'
    for name, data in members:
        header = f'{name + "/":<16}{0:<12}{0:<6}{0:<6}{"100644":<8}{len(data):<10}`\n'
        result += header.encode() + data + (b'\n' if len(data) % 2 else b'')
    return result


class UpdateMetadataTests(unittest.TestCase):
    def test_upload_urgency_case_and_comment_are_preserved(self):
        result = upload_metadata(changes('EMERGENCY (regression fix)'), CONTROL, sha(b'test'), 4)
        self.assertEqual(result['urgency'], 'emergency')
        self.assertEqual(result['urgency_raw'], 'EMERGENCY (regression fix)')
        self.assertIsNone(result['vulnerability_severity'])
        self.assertFalse(result['signature_verified'])
        self.assertEqual(upload_metadata(changes('critical'), CONTROL, sha(b'test'), 4)['urgency'], 'critical')

    def test_missing_urgency_is_unknown_not_low(self):
        raw = changes().replace(b'Urgency: emergency\n', b'')
        self.assertIsNone(upload_metadata(raw, CONTROL, sha(b'test'), 4)['urgency'])

    def test_exact_artifact_and_source_binding(self):
        for raw in (changes().replace(b'sample-src', b'other-src'),
                    changes().replace(b'1:2.0-3)', b'1:2.0-4)'),
                    changes().replace(b'Architecture: amd64', b'Architecture: all'),
                    changes().replace(b'Binary: sample-bin', b'Binary: other-bin'),
                    changes().replace(sha(b'test').encode(), sha(b'other').encode()),
                    changes().replace(b' 4 sample.deb', b' 5 sample.deb'),
                    changes().replace(b' 4 sample.deb', b' 4 ../sample.deb'),
                    changes('urgent'), changes() + b'Urgency: low\n'):
            with self.assertRaises(Invalid):
                upload_metadata(raw, CONTROL, sha(b'test'), 4)

    def test_source_version_not_binary_rebuild_version(self):
        self.assertEqual(source_identity(CONTROL), ('sample-src', '1:2.0-3'))
        self.assertEqual(source_identity({'package': 'sample', 'version': '2.0'}), ('sample', '2.0'))
        result = advisory_matches(DSA, *source_identity(CONTROL))
        self.assertEqual(result[0]['version_relation'], 'at-or-above-announced-fix')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['mentioned_issue_ids'], ['CVE-2026-90000', 'CVE-2026-90001'])

    def test_native_version_order_and_release_selection(self):
        for version in ('1:2.0-3~rc1', '2.0-999'):
            self.assertEqual(advisory_matches(DSA, 'sample-src', version)[0]['version_relation'],
                             'below-announced-fix')
        self.assertEqual(advisory_matches(DSA, 'other-src', '1'), [])
        self.assertEqual(advisory_matches(DSA.replace(b'[trixie]', b'[sid]'), 'sample-src', '1'), [])

    def test_malformed_and_ambiguous_advisories_rejected(self):
        for raw in (DSA + DSA, b'\t[trixie] - sample-src 1\n',
                    DSA.replace(b'1:2.0-3', b'<unfixed>'),
                    DSA + b'\t[trixie] - sample-src 1:2.0-4\n',
                    DSA.replace(b'CVE-2026-90000', b'bad-id')):
            with self.assertRaises(Invalid):
                advisory_matches(raw, 'sample-src', '1:2.0-3')

    def test_real_deb_intake_keeps_observation_separate_from_trust(self):
        deb = deb_fixture()
        result = inspect_update(deb, changes(artifact=deb), DSA)
        self.assertEqual(result['upload']['urgency'], 'emergency')
        self.assertEqual(result['advisory_matches'][0]['advisory_id'], 'DSA-90000-1')
        self.assertEqual(result['security_assessment'], 'not-established')
        self.assertFalse(result['archive_authenticated'])
        self.assertFalse(result['advisories_authenticated'])
        self.assertFalse(result['execution_permit'])
        empty = inspect_update(deb)
        self.assertIsNone(empty['upload'])
        self.assertEqual(empty['advisory_matches'], [])
        self.assertEqual(empty['security_assessment'], 'not-established')


if __name__ == '__main__':
    unittest.main()
