# SPDX-License-Identifier: MIT
import json, shutil, subprocess
from pathlib import Path
repo = Path('/home/nia/devbox/niaos/nia-os-consent')
work = repo.parent / '.work/native-generation-transition-01'
dest = work / 'reference-snapshot'
dest.mkdir()
for src, name in [('debug-root', 'root'), ('debug-state', 'state'), ('debug-cas', 'cas'), ('debug-bank', 'bank')]:
    tree = work / src
    for file in sorted(tree.rglob('*')):
        assert not file.is_symlink(), file
        if not file.is_file():
            continue
        assert file.stat().st_size <= 1024 * 1024, file
        target = dest / name / file.relative_to(tree)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)
(dest / 'media').mkdir()
for name in ['empty.deb', 'consumer-upgrade.deb']:
    shutil.copy2(repo / 'pkgcore/tests/fixtures/selected-catalog' / name, dest / 'media' / name)
shutil.copy2(work / 'debug-build.log', dest / 'native.log')
subprocess.run(['python3', '-B', str(repo / 'pkgcore/tests/compare_current_catalog.py'),
                '--root', str(dest / 'root'), '--state', str(dest / 'state'),
                '--cas', str(dest / 'cas'), '--bank', str(dest / 'bank'),
                '--media', str(dest / 'media'), '--native', str(dest / 'native.log'),
                '--output', str(work / 'reference-snapshot-result.json')], check=True)
