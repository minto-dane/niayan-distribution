#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Stage distribution inputs; never edit component or upstream source trees."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
DIST = HERE.parent
COMPONENTS = ('assurance', 'pkgcore', 'statecore', 'controlcore',
              'configcore', 'resolvercore', 'capsulecore')


def write(path, text, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)


def stage_component(workspace, dest, component):
    source = workspace / component
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=source):
        raise ValueError(f'commit component changes before packaging: {component}')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    manifest = {}
    # Include exact tracked sources, contracts, tests and build tools; evidence is
    # published separately. No vendored code is regenerated or patched here.
    exported = subprocess.check_output(['git', 'archive', '--format=tar', commit], cwd=source)
    with tarfile.open(fileobj=io.BytesIO(exported)) as archive:
        for member in archive:
            name = member.name
            path = Path(name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('invalid Git archive path')
            if not name or path.parts[0] in {'evidence', 'history', '.github'}:
                continue
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError(f'non-regular package source: {name}')
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            data = archive.extractfile(member).read()
            target.write_bytes(data)
            target.chmod(0o755 if member.mode & 0o111 else 0o644)
            manifest[name] = hashlib.sha256(data).hexdigest()
    version = '0.1.0+git' + commit[:12]
    package = 'niaos-' + component
    debian = dest / 'debian'
    write(debian / 'control', f'''Source: {package}
Section: admin
Priority: optional
Maintainer: NiaOS Developers <developers@niaos.invalid>
Build-Depends: debhelper-compat (= 13), gnat, gprbuild, python3,
 libsodium-dev, libarchive-dev, libcurl4-openssl-dev, libxml2-dev, libsystemd-dev
Standards-Version: 4.7.2
Rules-Requires-Root: no

Package: {package}
Architecture: amd64
Depends: ${{shlibs:Depends}}, ${{misc:Depends}}
Description: NiaOS {component} development tools
 Independently maintained NiaOS component, built from its recorded Git commit.
 These tools do not replace APT/dpkg or automatically activate host services.
''')
    write(debian / 'changelog', f'''{package} ({version}) unstable; urgency=medium

  * Package unmodified component commit {commit}.

 -- NiaOS Developers <developers@niaos.invalid>  Mon, 07 Sep 2026 00:00:00 +0000
''')
    write(debian / 'source/format', '3.0 (native)\n')
    write(debian / 'rules', '''#!/usr/bin/make -f
export DH_VERBOSE = 1
%:
	dh $@
override_dh_auto_configure:
override_dh_auto_build:
	$(MAKE) build JOBS=1
override_dh_auto_test:
	$(MAKE) test JOBS=1
override_dh_auto_install:
override_dh_auto_clean:
	rm -rf build
''', 0o755)
    artifact = json.loads((dest / 'packaging/nia/artifact.json').read_text())
    write(debian / (package + '.install'), ''.join(
        f"{row['source']} {str(Path(row['destination']).parent)}\n"
        for row in artifact['executables']))
    shutil.copy2(dest / 'LICENSE', debian / 'copyright')
    write(dest / 'nia-source.json', json.dumps({'component': component, 'commit': commit,
          'files': manifest}, indent=2) + '\n')
    write(debian / (package + '.docs'), 'nia-source.json\n')
    return {'component': component, 'commit': commit, 'package': package, 'version': version}


def prepare(output, workspace, desktop):
    lock = json.loads((HERE / 'lock.json').read_text())
    output.mkdir(parents=True, exist_ok=False)
    package_dir = output / 'packages'
    package_dir.mkdir()
    integration = package_dir / 'niaos-integration'
    shutil.copytree(DIST / 'packaging/integration', integration)
    shutil.copy2(DIST / 'LICENSE', integration / 'debian/copyright')
    for name in ('rules', 'niaos-release.preinst', 'niaos-release.postrm'):
        (integration / 'debian' / name).chmod(0o755)
    components = [stage_component(workspace, package_dir / ('niaos-' + name), name)
                  for name in COMPONENTS]
    live = output / 'live'
    shutil.copytree(HERE / 'auto', live / 'auto')
    (live / 'auto/config').chmod(0o755)
    for hook in sorted((HERE / 'hooks').glob('*.hook.chroot')):
        write(live / 'config/hooks/live' / hook.name, hook.read_text(), 0o755)
    # APT and AppStream regenerate these local caches. Their content differs
    # between clean builds; use live-build's standard rootfs exclusions.
    write(live / 'config/rootfs/excludes',
          'var/cache/apt/pkgcache.bin\nvar/cache/apt/srcpkgcache.bin\n'
          'var/cache/swcatalog/cache/C-*.xb\n')
    environment = {'NIA_SNAPSHOT': lock['snapshot'], 'SOURCE_DATE_EPOCH': lock['source_date_epoch'],
                   'NIA_RELEASE': lock['release'], 'NIA_CODENAME': lock['distribution'],
                   'NIA_ARCHITECTURE': lock['architecture'],
                   'NIA_ARCHIVE_AREAS': ' '.join(lock['archive_areas']),
                   'NIA_BOOTLOADERS': ' '.join(lock['bootloaders']),
                   'NIA_SECURE_BOOT': lock['secure_boot'], 'NIA_INSTALLER': lock['installer']}
    write(live / 'nia-image.env', ''.join(k + '=' + shlex.quote(str(v)) + '\n'
                                        for k, v in environment.items()))
    # Expiry override is confined to build-time historical archives. The final
    # live/installed system gets current mirrors and normal expiry validation.
    write(live / 'config/apt/apt.conf', 'Acquire::Check-Valid-Until "false";\n'
          'Acquire::ForceIPv4 "true";\nAcquire::http::Timeout "30";\n'
          'Acquire::https::Timeout "30";\n')
    meta = 'niaos-base' if desktop == 'server' else 'niaos-desktop-' + desktop
    write(live / 'config/package-lists/niaos.list.chroot', meta + '\n' +
          '\n'.join(row['package'] for row in components) + '\n')
    write(live / 'config/package-lists/live.list.chroot_live',
          'live-boot\nlive-config\nlive-config-systemd\n')
    distribution_inputs = {}
    # Acceptance and source-collection tools record their own hashes. They are
    # not inputs to the ISO payload, so their diagnostics can evolve separately.
    reporting_tools = {'vm_console.py', 'collect-sources.py', 'record-build.py'}
    for root in (HERE, DIST / 'packaging/integration'):
        for path in sorted(root.rglob('*')):
            if '__pycache__' in path.parts or path.suffix == '.pyc':
                continue
            if root == HERE and (path.suffix == '.md' or path.name.startswith('test')
                                 or path.name in reporting_tools or 'fixtures' in path.parts):
                continue
            if path.is_symlink():
                raise ValueError(f'non-regular distribution input: {path}')
            if path.is_file():
                distribution_inputs[str(path.relative_to(DIST))] = hashlib.sha256(path.read_bytes()).hexdigest()
    distribution_inputs['LICENSE'] = hashlib.sha256((DIST / 'LICENSE').read_bytes()).hexdigest()
    write(output / 'input-manifest.json', json.dumps({'lock': lock, 'desktop': desktop,
          'components': components, 'distribution_inputs': distribution_inputs,
          'upstream_source_patches': []}, indent=2) + '\n')
    # SOURCE_DATE_EPOCH is also consumed by dpkg-source and live-build.
    for path in sorted(output.rglob('*'), reverse=True):
        if path.is_dir():
            path.chmod(0o755)
        elif path.is_file():
            path.chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)
        os.utime(path, (lock['source_date_epoch'], lock['source_date_epoch']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=DIST.parent)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--desktop', choices=('kde', 'gnome', 'server'), default='kde')
    args = parser.parse_args()
    prepare(args.output.resolve(), args.workspace.resolve(), args.desktop)
