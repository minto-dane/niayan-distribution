# SPDX-License-Identifier: MIT
"""Development-only real TUF/OpenPGP -> scoped receipt -> native CAS check."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

import test_archive_receipt as fixtures
from deb_archive import ar_members, decompress, tar_inventory, MAX_CONTROL
from archive_receipt import scope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise SystemExit('Use an unprivileged isolated test container')
    driver = args.driver.resolve(strict=True)
    fixtures.ReceiptTests.setUpClass()
    case = fixtures.ReceiptTests()
    try:
        case.setUp()
        with case.remote.client(case.cache) as repository:
            receipt = case.issue(repository)
            expected_scope = bytes.fromhex(scope(repository, case.target))
        original = case.fixture.fixture.deb
        control = tar_inventory(decompress(*ar_members(original)[1], MAX_CONTROL), control=True)[1]['control']
        artifacts = {'receipt': receipt.wire, 'policy': receipt.policy_bytes, 'original.deb': original,
                     'control': control, 'InRelease': case.fixture.signed, 'Packages': case.fixture.fixture.packed,
                     'keyring': case.fixture.fixture.keyring, 'public-key': case.public_key, 'scope': expected_scope}
        with tempfile.TemporaryDirectory(prefix='nia-archive-bridge-') as temporary:
            root = Path(temporary)
            for name in ('accepted', 'wrong-key', 'wrong-scope', 'different-control', 'damaged-receipt'):
                directory = root/name
                media, store = directory/'media', directory/'store'
                media.mkdir(mode=0o700, parents=True)
                store.mkdir(mode=0o700)
                contents = dict(artifacts)
                field = {'wrong-key': 'public-key', 'wrong-scope': 'scope',
                         'different-control': 'control', 'damaged-receipt': 'receipt'}.get(name)
                if field:
                    contents[field] = bytes([contents[field][0] ^ 1])+contents[field][1:]
                for filename, raw in contents.items():
                    (media/filename).write_bytes(raw)
                result = subprocess.run([str(driver), str(store), str(media), 'external'],
                                        text=True, capture_output=True, timeout=60)
                if name == 'accepted':
                    if result.returncode:
                        raise RuntimeError('native bridge rejected authenticated originals: '+result.stdout+result.stderr)
                    expected = {'SUPPLY_RECEIPT': receipt.wire, 'SUPPLY_ORIGINAL': original, 'SUPPLY_CONTROL': control}
                    for label, raw in expected.items():
                        line = label+' '+hashlib.sha256(raw).hexdigest()
                        if line not in result.stdout.splitlines():
                            raise RuntimeError('native hash binding differs: '+label)
                    print(result.stdout, end='')
                elif result.returncode == 0:
                    raise RuntimeError('native bridge accepted '+name)
                print('PASS archive receipt bridge '+name, flush=True)
    finally:
        case.doCleanups()
        fixtures.ReceiptTests.tearDownClass()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
