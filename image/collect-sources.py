#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Collect exact sources; record APT and historical HTTPS provenance separately."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import tempfile


def source_identity(package):
    value = subprocess.check_output(['dpkg-deb', '--show',
        '--showformat=${Package}\t${Version}\t${Source}\n', str(package)], text=True)
    name, version, source = value.rstrip('\n').split('\t')
    if source:
        match = re.fullmatch(r'([a-z0-9][a-z0-9+.-]+)(?: \(([^()\s]+)\))?', source)
        if not match:
            raise ValueError('unsupported Source field in ' + str(package))
        name = match[1]
        version = match[2] or version
    if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]+', name):
        raise ValueError('invalid source package name')
    if not re.fullmatch(r'[0-9][A-Za-z0-9.+:~\-]*', version):
        raise ValueError('invalid source version')
    return name, version


def source_references(package):
    references = {source_identity(package)}
    fields = subprocess.check_output(['dpkg-deb', '--show',
        '--showformat=${Built-Using},${Static-Built-Using}', str(package)], text=True)
    for field in fields.split(','):
        if not field.strip():
            continue
        match = re.fullmatch(r'\s*([a-z0-9][a-z0-9+.-]+)\s*\(=\s*'
                             r'([0-9][A-Za-z0-9.+:~\-]*)\s*\)\s*', field)
        if not match:
            raise ValueError('non-exact additional source reference in ' + str(package))
        references.add((match[1], match[2]))
    return sorted(references)


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def binary_identity(path):
    return tuple(subprocess.check_output(['dpkg-deb', '--show',
        '--showformat=${Package}\t${Version}', str(path)], text=True).split('\t'))


def installer_identity(version):
    match = re.fullmatch(r'cdrom-(?:isolinux|gtk)-([0-9][A-Za-z0-9.+:~\-]*)', version)
    if not match:
        raise ValueError('unrecognized installer source version: ' + version)
    return 'debian-installer', match[1]


def verify_live_inventory(build, binary_index):
    inventories = list((build / 'live').glob('*.packages'))
    if len(inventories) != 1:
        raise ValueError('expected one completed Live package inventory')
    path = inventories[0]
    packages = []
    for line in path.read_text().splitlines():
        package, version = line.split()
        name, _, architecture = package.partition(':')
        if architecture not in {'', 'amd64', 'all'}:
            raise ValueError('unsupported Live package architecture')
        packages.append((name, version))
    if not packages:
        raise ValueError('Live package inventory is empty')
    missing = sorted(set(packages) - set(binary_index))
    if missing:
        raise ValueError('Live packages missing from source associations: ' + repr(missing))
    return {'path': str(path.relative_to(build)), 'sha256': file_digest(path),
            'packages': len(packages), 'missing_binary_associations': []}


def initrd_inventory(path):
    # Extract only dpkg's inventory using the standard archive tool. Never
    # unpack installer paths into the host or execute their scripts.
    with tempfile.TemporaryFile() as archive, gzip.open(path, 'rb') as stream:
        size = 0
        while block := stream.read(1024**2):
            size += len(block)
            if size > 1024**3:
                raise ValueError('installer initrd exceeds the collection budget')
            archive.write(block)
        archive.seek(0)
        status = subprocess.run(['cpio', '-i', '--to-stdout',
            'var/lib/dpkg/status', './var/lib/dpkg/status'], stdin=archive,
            capture_output=True, check=True).stdout.decode()
    rows = []
    for paragraph in status.split('\n\n'):
        name = re.search(r'^Package: (.+)$', paragraph, re.M)
        version = re.search(r'^Version: (.+)$', paragraph, re.M)
        if name and version:
            if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]+', name[1]):
                raise ValueError('invalid embedded package name')
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+:~\-]*', version[1]):
                raise ValueError('invalid embedded package version')
            rows.append((name[1], version[1]))
    if not rows:
        raise ValueError('installer package inventory is empty')
    return rows


def historical_download(target, name, version, binary=False):
    # Debian's standard client retrieves exact historical packages over HTTPS.
    # These are source-collection inputs, never installed or executed here.
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='nia-debsnap-') as temporary:
        (Path(temporary) / '.devscripts').write_text(
            "DEBSNAP_BASE_URL='https://snapshot.debian.org'\n")
        # Installer status omits Architecture. debsnap treats multiple requested
        # architectures as requirements, not alternatives. Try amd64, then all
        # only when the exact amd64 identity is explicitly absent.
        for architecture in (('amd64', 'all') if binary else (None,)):
            download = Path(temporary) / (architecture or 'source')
            command = ['debsnap', '--destdir', str(download)]
            if architecture:
                command += ['--architecture', architecture]
            print('Historical download: ' + name + '=' + version
                  + ' (' + (architecture or 'source') + ')', flush=True)
            fetched = subprocess.run([*command, name, version],
                env={**os.environ, 'HOME': temporary, 'LC_ALL': 'C'},
                timeout=900, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            print(fetched.stdout, end='', flush=True)
            absent = f'No binary packages found for {name} version {version} on amd64'
            if architecture == 'amd64' and fetched.returncode == 2 and absent in fetched.stdout:
                continue
            fetched.check_returncode()
            break
        for path in sorted(download.iterdir()):
            if not path.is_file() or path.is_symlink():
                raise ValueError('unexpected historical download')
            destination = target / path.name
            if destination.is_symlink():
                raise ValueError('historical destination is a symlink')
            if destination.exists() and file_digest(destination) != file_digest(path):
                raise ValueError('historical download changed: ' + path.name)
            shutil.copyfile(path, destination)


def verify_source_archives(target, name, version):
    controls = list(target.glob('*.dsc'))
    if len(controls) != 1:
        raise ValueError('expected one source control file')
    text = controls[0].read_text()
    if not re.search(r'^Source: ' + re.escape(name) + r'$', text, re.M):
        raise ValueError('source name mismatch')
    if not re.search(r'^Version: ' + re.escape(version) + r'$', text, re.M):
        raise ValueError('source version mismatch')
    checksums = re.search(r'^Checksums-Sha256:\n((?: .+\n)+)', text, re.M)
    if not checksums:
        raise ValueError('source control lacks SHA-256 archive checksums')
    for line in checksums[1].splitlines():
        digest, size, filename = line.split()
        if Path(filename).name != filename or filename in {'.', '..'}:
            raise ValueError('invalid source archive path')
        path = target / filename
        if not path.is_file() or path.is_symlink() or path.stat().st_size != int(size) or file_digest(path) != digest:
            raise ValueError('source archive checksum mismatch: ' + filename)


def add_embedded_sources(build, output, packages, binary_index):
    records = []
    for relative in ('live/binary/install/initrd.gz', 'live/binary/install/gtk/initrd.gz'):
        initrd = build / relative
        record = {'path': relative, 'sha256': file_digest(initrd), 'packages': []}
        for name, version in initrd_inventory(initrd):
            row = {'name': name, 'version': version}
            if name == 'debian-installer':
                references = [installer_identity(version)]
                row['association'] = 'installer build identity in embedded dpkg status'
            else:
                key = name, version
                if key not in binary_index:
                    target = output / 'installer-binaries' / name / version.replace(':', '%3a')
                    historical_download(target, name, version, binary=True)
                    candidates = list(target.glob('*.udeb'))
                    if len(candidates) != 1 or binary_identity(candidates[0]) != key:
                        raise ValueError('historical installer binary identity mismatch')
                    binary_index[key] = candidates[0]
                package = binary_index[key]
                references = source_references(package)
                row['binary_sha256'] = file_digest(package)
                row['association'] = 'exact binary package control fields'
            row['sources'] = [list(source) for source in references]
            record['packages'].append(row)
            for source in references:
                packages.setdefault(source, []).append(relative + '#' + name + '@' + version)
        records.append(record)
    return records


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build', type=Path, default=Path('/build'))
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--resume', action='store_true', help='resume the same recorded build after interruption')
    ap.add_argument('--include-installer', action='store_true',
                    help='also collect embedded initrd package sources; requires Debian devscripts/debsnap')
    args = ap.parse_args()
    if os.getuid() != 0 or not Path('/etc/niaos-image-builder').is_file():
        raise ValueError('dedicated disposable builder VM required')
    if args.include_installer and not shutil.which('debsnap'):
        raise ValueError('install devscripts from the fixed builder snapshot for embedded installer sources')
    build = args.build.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=args.resume)
    report_file = output / 'report.json'
    previous = json.loads(report_file.read_text()) if args.resume else None
    lists = output / 'apt-lists'
    (lists / 'partial').mkdir(parents=True, exist_ok=args.resume)
    lock = json.loads((Path(__file__).parent / 'lock.json').read_text())
    collector_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    input_digest = hashlib.sha256((build / 'input-manifest.json').read_bytes()).hexdigest()
    images = [{'path': str(path.relative_to(build)), 'sha256': file_digest(path)}
              for path in sorted((build / 'live').glob('*.iso'))]
    if args.include_installer and not images:
        raise ValueError('completed ISO required for embedded installer collection')
    if previous is not None and (previous.get('input_manifest_sha256') != input_digest
                                 or previous.get('collector_sha256') != collector_digest
                                 or previous.get('lock') != lock
                                 or previous.get('images') != images
                                 or previous.get('include_installer', False) != args.include_installer):
        raise ValueError('resume inputs differ from the recorded source collection')
    areas = ' '.join(lock['archive_areas'])
    snapshot = lock['snapshot']
    sources = output / 'debian.sources.list'
    sources.write_text('\n'.join(
        f'deb-src [check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] '
        f'http://snapshot.debian.org/archive/{archive}/{snapshot}/ {suite} {areas}'
        for archive, suite in [('debian', 'trixie'), ('debian', 'trixie-updates'),
                               ('debian-security', 'trixie-security')]) + '\n')
    apt = ['apt-get', '-o', 'Dir::Etc::sourcelist=' + str(sources),
           '-o', 'Dir::Etc::sourceparts=-', '-o', 'Dir::State::Lists=' + str(lists),
           '-o', 'Acquire::ForceIPv4=true', '-o', 'Acquire::http::Timeout=30',
           '-o', 'Acquire::Retries=2', '-o', 'APT::Update::Error-Mode=any',
           '-o', 'APT::Get::AllowUnauthenticated=false']
    subprocess.run([*apt, 'update'], check=True)
    packages = {}
    binary_index = {}
    roots = [build / 'live/cache', build / 'live/binary', build / 'packages']
    for root in roots:
        for pattern in ('*.deb', '*.udeb'):
            for package in sorted(root.rglob(pattern)):
                if package.is_symlink():
                    continue
                binary_index[binary_identity(package)] = package
                for name, version in source_references(package):
                    packages.setdefault((name, version), []).append(str(package.relative_to(build)))
    if not packages:
        raise ValueError('no binary package inventory found')
    report = previous or {'result': 'incomplete',
              'scope': 'cached binary/installer packages including Built-Using and Static-Built-Using',
              'lock': lock, 'input_manifest_sha256': input_digest,
              'collector_sha256': collector_digest,
              'images': images,
              'include_installer': args.include_installer,
              'sources': [], 'production_qualified': False,
              'firmware_note': 'Non-free firmware source packages can contain opaque firmware blobs.'}
    report['result'] = 'incomplete'
    report['live_inventory'] = verify_live_inventory(build, binary_index)

    def save():
        temporary = report_file.with_suffix('.json.tmp')
        with temporary.open('w') as stream:
            stream.write(json.dumps(report, indent=2) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, report_file)
        directory = os.open(output, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    save()
    if args.include_installer:
        embedded = add_embedded_sources(build, output, packages, binary_index)
        if previous and 'installer' in previous and previous['installer'] != embedded:
            raise ValueError('embedded installer inputs changed')
        report['installer'] = embedded
        report['scope'] = ('cached binary/installer packages including Built-Using and Static-Built-Using; '
                           'embedded text/GUI initrds and debian-installer build source')
        report['historical_transport'] = 'Debian debsnap HTTPS; source archive SHA-256 checked against DSC; not an APT archive signature claim'
        report['historical_tools'] = subprocess.check_output(
            ['dpkg-query', '-W', 'devscripts', 'libwww-perl', 'liblwp-protocol-https-perl'],
            text=True).splitlines()
        save()
    completed = {(row['name'], row['version']): row for row in report['sources']}
    if set(completed) - set(packages):
        raise ValueError('recorded binary inventory is no longer present')
    for (name, version), binaries in sorted(packages.items()):
        if (name, version) in completed:
            row = completed[(name, version)]
            if row['binaries'] != binaries:
                raise ValueError('binary associations changed for ' + name)
            for file in row['files']:
                path = (output / file['path']).resolve(strict=True)
                if not path.is_relative_to(output):
                    raise ValueError('recorded source path outside output')
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                if path.stat().st_size != file['size'] or digest != file['sha256']:
                    raise ValueError('recorded source archive changed: ' + str(path))
            continue
        if shutil.disk_usage(output).free < 4 * 1024**3:
            raise ValueError('less than 4 GiB free in builder; source collection stopped')
        target = output / 'packages' / name / version.replace(':', '%3a')
        target.mkdir(parents=True, exist_ok=args.resume)
        if name.startswith('niaos-'):
            provenance = 'native source package produced with the recorded component build'
            dsc = build / 'packages' / f'{name}_{version}.dsc'
            if not dsc.is_file():
                raise ValueError('missing first-party source control: ' + str(dsc))
            with tempfile.TemporaryDirectory(prefix='nia-source-check-') as temporary:
                subprocess.run(['dpkg-source', '-x', str(dsc),
                                str(Path(temporary) / 'source')], check=True)
            shutil.copy2(dsc, target / dsc.name)
            # Native first-party packages contain their complete source here.
            archive = build / 'packages' / f'{name}_{version}.tar.xz'
            if not archive.is_file():
                raise ValueError('missing first-party source archive: ' + str(archive))
            shutil.copy2(archive, target / archive.name)
        else:
            provenance = 'signed APT snapshot'
            apt_user = pwd.getpwnam('_apt')
            os.chown(target, apt_user.pw_uid, apt_user.pw_gid)
            fetched = subprocess.run([*apt, '--download-only', '--only-source', 'source',
                name + '=' + version], cwd=target, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, env={**os.environ, 'LC_ALL': 'C'})
            print(fetched.stdout, end='', flush=True)
            if fetched.returncode:
                absent = ('Can not find version' in fetched.stdout
                          or 'Unable to find a source package' in fetched.stdout)
                if not args.include_installer or not absent:
                    fetched.check_returncode()
                historical_download(target, name, version)
                provenance = 'historical Debian snapshot HTTPS and DSC SHA-256; archive signature not verified by this retrieval'
        verify_source_archives(target, name, version)
        inventory = []
        for file in sorted(target.iterdir()):
            if not file.is_file() or file.is_symlink():
                raise ValueError('unexpected source output')
            with file.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            inventory.append({'path': str(file.relative_to(output)),
                              'size': file.stat().st_size, 'sha256': digest})
        if not any(row['path'].endswith('.dsc') for row in inventory):
            raise ValueError('source control missing after download')
        report['sources'].append({'name': name, 'version': version,
                                  'binaries': binaries, 'files': inventory,
                                  'provenance': provenance})
        save()
    report['result'] = ('pass-for-cached-and-embedded-package-inventory' if args.include_installer
                        else 'pass-for-cached-package-inventory')
    save()


if __name__ == '__main__':
    main()
