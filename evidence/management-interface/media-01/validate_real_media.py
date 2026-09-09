from pathlib import Path
import hashlib
import json
import os
import subprocess
from urllib.parse import unquote

root = Path('/work/original-media')
inputs = json.loads(Path('/work/original-media-inputs.json').read_text())
bindir = Path('/source/native/bin')
def run(command, args, language='C.UTF-8'):
    result = subprocess.run([str(bindir / command), *args], cwd=root,
                            env={'PATH': '', 'LC_ALL': language},
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert not result.stderr
    return result.stdout
assert run('inutoc', [str(root)]) == ''
index = (root / '.toc').read_bytes()
inode = (root / '.toc').stat().st_ino
assert run('inutoc', [str(root)]) == ''
assert (root / '.toc').stat().st_ino == inode
assert (root / '.toc').read_bytes() == index
first = run('installp', ['-L', '-d', str(root)])
second = run('geninstall', ['-L', '-d', str(root)], 'ja_JP.UTF-8')
assert first == second
lines = first.splitlines()
assert len(lines) == 8
observed = {}
for line in lines[1:]:
    columns = [unquote(field) for field in line.split(':')]
    assert len(columns) == 6
    observed[columns[4]] = columns[5]
for row in inputs['files']:
    assert observed[row['filename']] == row['sha256']
    assert hashlib.sha256((root / row['filename']).read_bytes()).hexdigest() == row['sha256']
human = run('installp', ['-l', '-d', str(root)], 'ja_JP.UTF-8')
assert '未検証' in human or '検証されていません' in human or '未確認' in human
Path('/work/media-human.txt').write_text(human)
Path('/work/media-colon.txt').write_text(first)
Path('/work/media-index.json').write_bytes(index)
Path('/work/real-media-result.json').write_text(json.dumps(dict(
    result='pass', artifact_count=7, original_bytes_unchanged=True,
    deterministic_rebuild=True, identical_rebuild_preserves_inode=True,
    installp_geninstall_colon_identical_across_locales=True,
    index_sha256=hashlib.sha256(index).hexdigest(),
    packages_installed=False, handlers_executed=False,
    publisher_authentication=False, production_qualified=False), indent=2)+'\n')
print('Seven preserved DEBs: indexing, rebuild, listing and original hash checks passed.')
