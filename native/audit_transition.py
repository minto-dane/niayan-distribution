#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Inventory an offline Debian root before designing its Nia-only replacement.

Reads status and retained control files; never calls APT/dpkg, runs maintainer
scripts, changes a root, or authorizes a transaction. Dependency results concern
the final package set only. Command mentions are review leads, not effect proofs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
from deb_archive import deb822, unfold, HOOKS
from debian_semantics import NAME, relations, provider_matches, split_version
from nia_common import Invalid, read_file, canonical

REMOVED = frozenset({
    'apt', 'apt-utils', 'aptitude', 'aptitude-common', 'dpkg', 'dpkg-dev',
    'libdpkg-perl', 'python3-apt', 'python-apt-common', 'unattended-upgrades',
    'packagekit', 'packagekit-tools', 'aptdaemon', 'synaptic',
    'plasma-discover-backend-packagekit',
})
COMMANDS = (
    'apt', 'apt-get', 'apt-cache', 'dpkg', 'dpkg-query', 'dpkg-divert',
    'dpkg-statoverride', 'dpkg-maintscript-helper', 'update-alternatives',
    'deb-systemd-helper', 'deb-systemd-invoke', 'invoke-rc.d', 'update-rc.d',
    'update-initramfs', 'update-grub', 'ldconfig', 'ucf', 'ucfr',
    'adduser', 'addgroup', 'useradd', 'groupadd', 'systemd-sysusers',
    'systemd-tmpfiles', 'update-mime-database', 'update-desktop-database',
    'glib-compile-schemas', 'update-icon-caches', 'fc-cache', 'setcap',
    'apparmor_parser', 'debconf', 'db_input', 'db_get',
)
TOKEN = re.compile(rb'(?<![A-Za-z0-9_+.-])(' +
                   b'|'.join(re.escape(x.encode()) for x in COMMANDS) +
                   rb')(?![A-Za-z0-9_+.-])')


def excluded(name):
    return name in REMOVED or name.startswith(('libapt-pkg', 'libapt-inst'))


def packages(raw):
    result = []
    seen = set()
    for record in deb822(raw):
        status = record.get('status', '')
        if status == 'deinstall ok config-files':
            # Residual configuration is accounted for separately by the caller.
            continue
        if status != 'install ok installed':
            raise Invalid('non-terminal or unsupported package state: ' + status)
        name = record.get('package', '')
        version = record.get('version', '')
        arch = record.get('architecture', '')
        if not NAME.fullmatch(name) or arch not in ('amd64', 'all'):
            raise Invalid('unsupported package identity: ' + name)
        if name in seen:
            raise Invalid('same-name coinstallation is not qualified: ' + name)
        seen.add(name)
        split_version(version)
        provides = [(a.name, a.version or None)
                    for group in relations(unfold(record.get('provides', '')), provides=True)
                    for a in group]
        result.append({'id': name, 'name': name, 'version': version,
                       'architecture': arch, 'multi_arch': record.get('multi-arch', 'no'),
                       'provides': provides, 'fields': record})
    if not result:
        raise Invalid('empty installed package inventory')
    return sorted(result, key=lambda p: p['name'])


def missing_dependencies(selected):
    # Build a capability index, then independently evaluate every original atom.
    # Do not drop a dependency just because its provider is being replaced.
    index = {}
    for package in selected:
        for name in {package['name'], *(p[0] for p in package['provides'])}:
            index.setdefault(name, []).append(package)
    missing = []
    for package in selected:
        for field in ('pre-depends', 'depends'):
            for group in relations(unfold(package['fields'].get(field, ''))):
                if not any(provider_matches(p, atom)
                           for atom in group for p in index.get(atom.name, [])):
                    missing.append({'package': package['name'], 'field': field,
                                    'alternatives': [a.__dict__ for a in group]})
    return missing


def inventory(status_path, info_path):
    raw = read_file(status_path, 16 * 1024**2)
    installed = packages(raw)
    if info_path.is_symlink() or not info_path.is_dir():
        raise Invalid('info must be an ordinary offline directory')
    info = {}
    for path in sorted(info_path.iterdir()):
        if len(info) >= 65536:
            raise Invalid('control inventory limit')
        # Stable names are kept for evidence, including non-hook control files.
        content = read_file(path, 16 * 1024**2)
        info[path.name] = {'sha256': hashlib.sha256(content).hexdigest(), 'size': len(content)}
    rows = []
    mentions = {}
    unique_paths = set()
    for p in installed:
        stem = p['name']
        qualified = stem + ':' + p['architecture']
        if (stem + '.list' in info) == (qualified + '.list' in info):
            raise Invalid('missing or ambiguous installed file list: ' + stem)
        prefix = qualified if qualified + '.list' in info else stem
        list_name = prefix + '.list'
        path_data = read_file(info_path / list_name, 16 * 1024**2)
        if hashlib.sha256(path_data).hexdigest() != info[list_name]['sha256']:
            raise Invalid('installed file list changed during inventory')
        listed_paths = path_data.decode('utf-8').splitlines()
        if any(not name.startswith('/') or '\x00' in name for name in listed_paths):
            raise Invalid('unsupported installed file list entry')
        unique_paths.update(listed_paths)
        effects = []
        for hook in sorted(HOOKS):
            name = prefix + '.' + hook
            if name not in info:
                continue
            content = read_file(info_path / name, 16 * 1024**2)
            if hashlib.sha256(content).hexdigest() != info[name]['sha256']:
                raise Invalid('control file changed during inventory')
            commands = sorted({m.group().decode('ascii') for m in TOKEN.finditer(content)})
            effects.append({'member': hook, **info[name], 'command_mentions': commands})
            for command in commands:
                mentions.setdefault(command, []).append(stem + ':' + hook)
        rows.append({'name': stem, 'version': p['version'], 'architecture': p['architecture'],
                     'essential': p['fields'].get('essential', 'no'),
                     'excluded_from_native_target': excluded(stem),
                     'effects': effects,
                     'conffiles': p['fields'].get('conffiles', ''),
                     'listed_path_count': len(listed_paths),
                     'control_prefix': prefix})
    selected = [p for p in installed if not excluded(p['name'])]
    if raw != read_file(status_path, 16 * 1024**2):
        raise Invalid('status changed during inventory')
    return {
        'schema': 'org.niaos.native-transition-inventory/v1',
        'scope': 'offline installed metadata; not an execution or migration permit',
        'status_sha256': hashlib.sha256(raw).hexdigest(),
        'control_inventory_sha256': hashlib.sha256(canonical(info)).hexdigest(),
        'control_inventory': info,
        'installed_count': len(installed),
        'residual_configurations': [r for r in deb822(raw)
                                    if r.get('status') == 'deinstall ok config-files'],
        'excluded_packages': [p['name'] for p in installed if excluded(p['name'])],
        'original_missing_dependencies': missing_dependencies(installed),
        'native_missing_dependencies': missing_dependencies(selected),
        'packages_with_retained_effects': sum(bool(r['effects']) for r in rows),
        'retained_effect_count': sum(len(r['effects']) for r in rows),
        'unique_listed_paths_including_directories': len(unique_paths),
        'command_mentions': dict(sorted(mentions.items())),
        'packages': rows,
        'limitations': [
            'status/control files are not authenticated original DEB inputs',
            'mentions include comments and do not establish executed effects',
            'no payload, generated-file, implicit-trigger or live-code coverage',
            'dependencies are final-set checks, not phase/schedule validation',
            'no effect is accepted by absence of a retained script',
        ],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--status', type=Path, required=True)
    ap.add_argument('--info', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    report = inventory(args.status, args.info)
    report['tool_sha256'] = {
        'native/audit_transition.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        **{'tools/' + name: hashlib.sha256((TOOLS / name).read_bytes()).hexdigest()
           for name in ('deb_archive.py', 'debian_semantics.py', 'nia_common.py')},
    }
    # A fresh evidence file is required. Never overwrite a previous observation.
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write('\n')
    print(json.dumps({k: report[k] for k in (
        'installed_count', 'packages_with_retained_effects', 'retained_effect_count',
        'excluded_packages')}))
    print('unsatisfied relations after exclusion:', len(report['native_missing_dependencies']))


if __name__ == '__main__':
    main()
