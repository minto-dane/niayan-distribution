#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Record completed build artifacts and the actual staged recipe, outside Git."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def identity(path, root):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path.relative_to(root)), 'size': path.stat().st_size, 'sha256': digest}


def compare_images(build, other, artifacts):
    first_manifest = (build / 'input-manifest.json').read_bytes()
    second_manifest = (other / 'input-manifest.json').read_bytes()
    rows = []
    first_paths = {row['path'] for row in artifacts if row['path'].endswith('.iso')}
    second_paths = {str(path.relative_to(other)) for path in (other / 'live').glob('*.iso')}
    for relative in sorted(first_paths | second_paths):
        paths = [root / relative for root in (build, other)]
        if any(not path.is_file() or path.is_symlink() for path in paths):
            rows.append({'path': relative, 'identical': False,
                         'reason': 'missing or non-regular ISO'})
            continue
        first = next(row for row in artifacts if row['path'] == relative)
        second = identity(paths[1], other)
        compared = subprocess.run(['cmp', '--silent', str(paths[0]), str(paths[1])])
        rows.append({'path': relative, 'first': first, 'second': second,
                     'byte_comparison_exit': compared.returncode,
                     'identical': first == second and compared.returncode == 0})
    equal_inputs = first_manifest == second_manifest
    return {'result': 'pass' if equal_inputs and rows and all(row['identical'] for row in rows) else 'fail',
            'input_manifests_identical': equal_inputs,
            'first_input_manifest_sha256': hashlib.sha256(first_manifest).hexdigest(),
            'second_input_manifest_sha256': hashlib.sha256(second_manifest).hexdigest(),
            'images': rows, 'comparison_tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'these two recorded builds; does not certify other machines or future inputs'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=Path('/build'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare-with', type=Path,
                        help='also compare actual ISO bytes and input manifest with another completed build')
    args = parser.parse_args()
    build = args.build.resolve(strict=True)
    output = args.output.resolve()
    isos = sorted((build / 'live').glob('*.iso'))
    if not isos or any(not p.is_file() or p.is_symlink() for p in isos):
        raise ValueError('completed regular ISO artifacts are required')
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(build / 'input-manifest.json', output / 'input-manifest.json')
    # Preserve the recipe that live-build actually used, including generated
    # configuration. Never copy VM seed, SSH keys, host home or cloud disk.
    for name in ('auto', 'config'):
        shutil.copytree(build / 'live' / name, output / name)
    shutil.copy2(build / 'live/nia-image.env', output / 'nia-image.env')
    for path in sorted((build / 'live').glob('*.packages*')):
        shutil.copy2(path, output / path.name)
    inventory = subprocess.check_output(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\n'])
    (output / 'builder-packages.tsv').write_bytes(inventory)
    artifacts = [identity(path, build) for path in isos]
    for path in sorted((build / 'packages').iterdir()):
        if path.is_file() and not path.is_symlink():
            artifacts.append(identity(path, build))
    configuration = [identity(path, output) for path in sorted(output.rglob('*'))
                     if path.is_file() and not path.is_symlink()]
    report = {'result': 'recorded', 'artifacts': artifacts,
              'staged_configuration': configuration,
              'claims': {'boot_tested': False, 'installed_tested': False,
                         'iso_bit_reproducible': False, 'production_qualified': False}}
    comparison = None
    if args.compare_with:
        other = args.compare_with.resolve(strict=True)
        if other == build:
            raise ValueError('comparison requires two different build directories')
        comparison = compare_images(build, other, artifacts)
        (output / 'iso-comparison.json').write_text(json.dumps(comparison, indent=2) + '\n')
        report['claims']['iso_bit_reproducible'] = comparison['result'] == 'pass'
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    if comparison and comparison['result'] != 'pass':
        raise SystemExit('ISO/input comparison failed; see iso-comparison.json')


if __name__ == '__main__':
    main()
