#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Export exact internal service sources into a new Debian source directory."""
import argparse
import hashlib
import json
from pathlib import Path
import stat


def prepare(destination):
    distribution = Path(__file__).resolve().parents[1]
    packaging = distribution / 'packaging/root-preparation'
    files = [(p, p.relative_to(packaging)) for p in sorted(packaging.rglob('*')) if not p.is_dir()]
    files += [(distribution / name, Path(name)) for name in
              ('native/root_bank.py', 'native/worker/root_extract.c', 'native/worker/Makefile')]
    # Review all inputs before creating a fresh output. No upstream patching,
    # recursive workspace export, installed-state discovery or hidden download.
    checked = []
    for source, relative in files:
        info = source.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 1024 * 1024:
            raise ValueError('source is not a bounded regular file: ' + str(relative))
        checked.append((source, relative, source.read_bytes(), 0o755 if info.st_mode & 0o111 else 0o644))
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    manifest = {}
    for source, relative, raw, mode in checked:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw); target.chmod(mode)
        manifest[str(relative)] = {'source': str(source.relative_to(distribution)),
                                  'sha256': hashlib.sha256(raw).hexdigest(), 'mode': mode}
    (destination / 'source-inputs.json').write_text(json.dumps({'format': 1, 'files': manifest}, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.output)
