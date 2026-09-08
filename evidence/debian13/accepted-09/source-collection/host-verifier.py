from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

WORK = Path('/home/nia/devbox/niaos/.work')
ROOT = WORK.parent / 'nia-os-consent'
ARTIFACTS = WORK / 'distro-artifacts-09'
BUNDLE = ARTIFACTS / 'corresponding-sources'
TOOLS = ARTIFACTS / 'source-tools-02'
report_path = BUNDLE / 'report.json'
report = json.loads(report_path.read_text())
assert report['result'] == 'pass-for-cached-and-embedded-package-inventory'
assert report['include_installer'] is True
assert report['live_inventory']['packages'] == 2239
assert report['live_inventory']['missing_binary_associations'] == []
assert [len(row['packages']) for row in report['installer']] == [99, 175]
assert report['images'] == [{'path': 'live/niaos-0.1.0-amd64.hybrid.iso',
    'sha256': 'd4c18dc0e2be653bf11a04db40db95ca0353322010133e068dda274bd4aa314b'}]

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

assert digest(TOOLS / 'collect-sources.py') == report['collector_sha256']
assert json.loads((TOOLS / 'lock.json').read_text()) == report['lock']
assert digest(ARTIFACTS / 'record-09/input-manifest.json') == report['input_manifest_sha256']
spec = importlib.util.spec_from_file_location('collector', TOOLS / 'collect-sources.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
completion_path = BUNDLE / 'signed-kernel-sources/report.json'
completion = json.loads(completion_path.read_text())
assert completion['result'] == 'pass'
assert completion['base_report_sha256'] == digest(report_path)
assert completion['collector_sha256'] == report['collector_sha256']
assert completion['images'] == report['images']
completion_tool = ARTIFACTS / 'source-completion-tools/complete-sources.py'
assert completion['completion_tool_sha256'] == digest(completion_tool)
spec = importlib.util.spec_from_file_location('completion_tool', completion_tool)
completer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(completer)
manifest = {}
sources = set()
rows = [(row, BUNDLE) for row in report['sources']]
rows += [(row, BUNDLE / 'signed-kernel-sources') for row in completion['sources']]
for row, root in rows:
    key = row['name'], row['version']
    assert key not in sources
    sources.add(key)
    assert row['files']
    if root == BUNDLE:
        assert row['binaries']
    target = root / 'packages' / row['name'] / row['version'].replace(':', '%3a')
    collector.verify_source_archives(target, *key)
    for file in row['files']:
        path = root / file['path']
        assert not path.is_symlink() and path.resolve().is_relative_to(BUNDLE.resolve())
        assert path.stat().st_size == file['size'] and digest(path) == file['sha256'], path
        relative = str(path.relative_to(BUNDLE))
        assert relative not in manifest
        manifest[relative] = {'size': file['size'], 'sha256': file['sha256']}
    assert {p.name for p in target.iterdir()} == {Path(f['path']).name for f in row['files']}
for inventory in report['installer']:
    for package in inventory['packages']:
        assert all(tuple(source) in sources for source in package['sources'])
assert {('linux', '6.12.94-1'), ('linux', '6.12.107-1')} <= sources
for row in report['sources']:
    if row['name'] == 'linux-signed-amd64':
        archive = next(BUNDLE / file['path'] for file in row['files'] if file['path'].endswith('.tar.xz'))
        assert set(completer.kernel_references(archive)) <= sources
assert len([name for name, version in sources if name.startswith('niaos-')]) == 8
result = {'result': 'pass', 'scope': 'independent host readback of complete source archives after VM collection',
    'iso_sha256': report['images'][0]['sha256'], 'collector_sha256': report['collector_sha256'],
    'collection_report_sha256': digest(report_path), 'input_manifest_sha256': report['input_manifest_sha256'],
    'completion_report_sha256': digest(completion_path), 'completion_tool_sha256': digest(completion_tool),
    'supplemental_source_packages': len(completion['sources']),
    'source_packages': len(sources), 'source_files': len(manifest),
    'source_bytes': sum(f['size'] for f in manifest.values()),
    'live_packages': 2239, 'embedded_installer_packages': [99, 175],
    'provenance': dict(Counter(row['provenance'] for row, root in rows)),
    'native_source_packages': 8, 'production_qualified': False}
(ARTIFACTS / 'source-verification.json').write_text(json.dumps(result, indent=2) + '\n')
(ARTIFACTS / 'source-files-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(result, indent=2))
