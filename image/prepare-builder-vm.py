#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Verify and prepare a disposable VM; requires qemu-img and xorriso."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--directory', type=Path, required=True)
ap.add_argument('--public-key', type=Path, required=True)
args = ap.parse_args()
directory = args.directory.resolve(strict=True)
lock = json.loads((Path(__file__).parent / 'builder-vm.json').read_text())
with (directory / 'base.qcow2').open('rb') as stream:
    if hashlib.file_digest(stream, 'sha512').hexdigest() != lock['sha512']:
        raise ValueError('Debian builder image checksum mismatch')
for name in ('builder.qcow2', 'seed.iso', 'seed'):
    if (directory / name).exists():
        raise ValueError('refusing to replace existing VM state: ' + name)
key = args.public_key.read_text().strip()
if not key.startswith('ssh-ed25519 ') or '\n' in key:
    raise ValueError('one dedicated Ed25519 public key required')
seed = directory / 'seed'
seed.mkdir()
config = {'users': [{'name': 'builder', 'groups': ['sudo'], 'shell': '/bin/bash',
                    'sudo': 'ALL=(ALL) NOPASSWD:ALL', 'lock_passwd': True,
                    'ssh_authorized_keys': [key]}], 'ssh_pwauth': False,
          'disable_root': True, 'package_update': False, 'package_upgrade': False,
          'write_files': [{'path': '/etc/niaos-image-builder', 'permissions': '0644',
                           'content': 'Disposable NiaOS image build VM\n'}]}
(seed / 'user-data').write_text('#cloud-config\n' + json.dumps(config, indent=2) + '\n')
(seed / 'meta-data').write_text('instance-id: niaos-builder-01\nlocal-hostname: niaos-builder\n')
subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', 'base.qcow2',
                'builder.qcow2', str(lock['disk_gib']) + 'G'], cwd=directory, check=True)
subprocess.run(['xorriso', '-as', 'mkisofs', '-V', 'cidata', '-J', '-r',
                '-o', str(directory / 'seed.iso'), str(seed)], check=True)
(directory / 'base-verification.json').write_text(json.dumps(lock | {'checksum_result': 'pass'}, indent=2) + '\n')
