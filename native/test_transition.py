# SPDX-License-Identifier: BSD-3-Clause
import tempfile
from pathlib import Path
import unittest

from audit_transition import inventory, missing_dependencies, packages, Invalid


def stanza(name, extra='', arch='amd64'):
    return (f'Package: {name}\nStatus: install ok installed\nVersion: 1.0\n'
            f'Architecture: {arch}\n{extra}\n').encode()


class TransitionTests(unittest.TestCase):
    def test_original_alternative_and_versioned_provides_preserved(self):
        raw = (stanza('consumer', 'Depends: unavailable | api (>= 2)\n') +
               stanza('provider', 'Provides: api (= 2)\n'))
        self.assertEqual(missing_dependencies(packages(raw)), [])
        raw = raw.replace(b'api (= 2)', b'api')
        self.assertEqual(len(missing_dependencies(packages(raw))), 1)

    def test_native_any_requires_multiarch_allowed(self):
        raw = stanza('consumer', 'Pre-Depends: provider:any\n') + stanza('provider')
        self.assertEqual(len(missing_dependencies(packages(raw))), 1)
        raw = stanza('consumer', 'Pre-Depends: provider:any\n') + stanza('provider', 'Multi-Arch: allowed\n')
        self.assertEqual(missing_dependencies(packages(raw)), [])

    def test_incomplete_or_duplicate_state_rejected(self):
        for raw in (stanza('sample').replace(b'install ok installed', b'install ok unpacked'),
                    stanza('sample') + stanza('sample', arch='all')):
            with self.assertRaises(Invalid):
                packages(raw)

    def test_real_control_inventory_and_removal_breakage(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            status = base / 'status'
            info = base / 'info'
            info.mkdir()
            status.write_bytes(stanza('apt') + stanza('consumer', 'Depends: apt\n'))
            (info / 'apt.list').write_text('/usr/bin/apt\n')
            (info / 'consumer.list').write_text('/usr/bin/consumer\n')
            (info / 'consumer.postinst').write_text('#!/bin/sh\ndpkg-query -W apt\n')
            report = inventory(status, info)
            self.assertEqual(report['original_missing_dependencies'], [])
            self.assertEqual(report['native_missing_dependencies'][0]['package'], 'consumer')
            self.assertEqual(report['excluded_packages'], ['apt'])
            self.assertEqual(report['retained_effect_count'], 1)
            self.assertEqual(report['unique_listed_paths_including_directories'], 2)
            self.assertIn('dpkg-query', report['command_mentions'])
            (info / 'apt.list').unlink()
            (info / 'apt.list').symlink_to(status)
            with self.assertRaises((Invalid, OSError)):
                inventory(status, info)

    def test_missing_file_lists_not_empty_success(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'status').write_bytes(stanza('sample'))
            (base / 'info').mkdir()
            with self.assertRaises(Invalid):
                inventory(base / 'status', base / 'info')


if __name__ == '__main__':
    unittest.main()
