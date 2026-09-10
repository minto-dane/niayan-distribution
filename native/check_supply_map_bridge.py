# SPDX-License-Identifier: MIT
"""Development-only real supply issuer -> exact native source map check."""
import argparse
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile

import test_archive_receipt as fixtures
from archive_receipt import scope
from deb_archive import ar_members, decompress, tar_inventory, MAX_CONTROL


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
        with tempfile.TemporaryDirectory(prefix='nia-supply-map-bridge-') as temporary:
            root = Path(temporary)
            media, store = root/'media', root/'store'
            media.mkdir(mode=0o700)
            store.mkdir(mode=0o700)
            for name, raw in artifacts.items():
                (media/name).write_bytes(raw)
            result = subprocess.run([str(driver), str(store), str(media), 'external'],
                                    text=True, capture_output=True, timeout=60)
            if result.returncode:
                raise RuntimeError('native source map failed: '+result.stdout+result.stderr)
            values = dict(line.split() for line in result.stdout.splitlines() if line.startswith('SUPPLY_'))
            if set(values) != {'SUPPLY_MAP', 'SUPPLY_CATALOG', 'SUPPLY_CLOSURE'}:
                raise RuntimeError('missing native map observations')
            # Independently encode initial construction's exact singleton set.
            wire = (b'NIASMAP1'+bytes([104])*16+bytes(64)+bytes.fromhex(values['SUPPLY_CATALOG'])
                    +bytes.fromhex(values['SUPPLY_CLOSURE'])+struct.pack('>Q', 1)
                    +hashlib.sha256(original).digest()+hashlib.sha256(control).digest()
                    +hashlib.sha256(receipt.wire).digest())
            if len(wire) != 256 or hashlib.sha256(wire).hexdigest() != values['SUPPLY_MAP']:
                raise RuntimeError('native source map does not bind the exact authenticated originals')
            print(result.stdout, end='')
            print('PASS real supply issuance -> native catalog/difference -> independently encoded map', flush=True)
    finally:
        case.doCleanups()
        fixtures.ReceiptTests.tearDownClass()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
