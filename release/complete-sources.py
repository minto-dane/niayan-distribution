#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Complete signed-kernel sources without changing the base collection record."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import tarfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def kernel_references(archive):
    # Debian's generated signing source declares the original Linux source in
    # binary control stanzas, although the installer udebs omit Built-Using.
    # Read one ordinary member; never extract paths or execute source scripts.
    with tarfile.open(archive) as source:
        member = source.getmember('source-template/debian/control')
        if not member.isfile() or not 0 < member.size <= 4 * 1024**2:
            raise ValueError('unexpected signed-kernel control member')
        control = source.extractfile(member).read().decode()
    fields = re.findall(r'^Built-Using: (.+)$', control, re.M)
    if not fields:
        raise ValueError('signed-kernel source lacks original source references')
    references = set()
    for field in fields:
        match = re.fullmatch(r'linux \(= ([0-9][A-Za-z0-9.+:~\-]*)\)', field)
        if not match:
            raise ValueError('unsupported signed-kernel source reference')
        references.add(('linux', match[1]))
    return sorted(references)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--collector', type=Path,
        default=Path(__file__).resolve().parents[1] / 'image/collect-sources.py')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if os.getuid() != 0 or not Path('/etc/niaos-image-builder').is_file():
        raise ValueError('dedicated disposable builder VM required')
    sources = args.sources.resolve(strict=True)
    base_path = sources / 'report.json'
    base = json.loads(base_path.read_text())
    if base['result'] != 'pass-for-cached-and-embedded-package-inventory':
        raise ValueError('completed base collection including embedded installers required')
    collector_path = args.collector.resolve(strict=True)
    if digest(collector_path) != base['collector_sha256']:
        raise ValueError('collector differs from the recorded base collection')
    spec = importlib.util.spec_from_file_location('collector', collector_path)
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    output = sources / 'signed-kernel-sources'
    output.mkdir(exist_ok=args.resume)
    report_path = output / 'report.json'
    binding = {'base_report_sha256': digest(base_path),
        'collector_sha256': digest(collector_path), 'completion_tool_sha256': digest(Path(__file__)),
        'images': base['images'], 'input_manifest_sha256': base['input_manifest_sha256']}
    previous = json.loads(report_path.read_text()) if args.resume else None
    if previous and any(previous.get(key) != value for key, value in binding.items()):
        raise ValueError('resume inputs differ from the recorded completion')
    if previous:
        for row in previous['sources']:
            for file in row['files']:
                path = output / file['path']
                if path.is_symlink() or not path.resolve().is_relative_to(output):
                    raise ValueError('invalid completed source path')
                if path.stat().st_size != file['size'] or digest(path) != file['sha256']:
                    raise ValueError('completed source archive changed')
    available = {(row['name'], row['version']): row for row in base['sources']}
    wrappers = []
    wanted = set()
    for row in base['sources']:
        if row['name'] != 'linux-signed-amd64':
            continue
        for file in row['files']:
            path = sources / file['path']
            if path.is_symlink() or not path.resolve().is_relative_to(sources):
                raise ValueError('invalid recorded source path')
            if path.stat().st_size != file['size'] or digest(path) != file['sha256']:
                raise ValueError('signed-kernel source archive changed')
        archives = [sources / file['path'] for file in row['files'] if file['path'].endswith('.tar.xz')]
        if len(archives) != 1:
            raise ValueError('expected one signed-kernel native source archive')
        references = kernel_references(archives[0])
        wrappers.append({'name': row['name'], 'version': row['version'],
            'archive_sha256': digest(archives[0]), 'sources': [list(key) for key in references]})
        wanted.update(references)
    if not wrappers:
        raise ValueError('expected signed amd64 kernels in this image profile')
    report = {**binding, 'result': 'incomplete', 'scope': 'original Linux sources for recorded signed amd64 kernels',
        'wrappers': wrappers, 'already_in_base': [], 'sources': [], 'production_qualified': False}

    def save():
        temporary = report_path.with_suffix('.json.tmp')
        with temporary.open('w') as stream:
            stream.write(json.dumps(report, indent=2) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, report_path)
        directory = os.open(output, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    save()
    lock = base['lock']
    if lock['distribution'] != 'trixie' or lock['architecture'] != 'amd64':
        raise ValueError('unsupported base image profile')
    snapshot = lock['snapshot']
    apt_sources = output / 'debian.sources.list'
    apt_sources.write_text('\n'.join(
        'deb-src [check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] '
        f'http://snapshot.debian.org/archive/{archive}/{snapshot}/ {suite} '
        + ' '.join(lock['archive_areas'])
        for archive, suite in [('debian', 'trixie'), ('debian', 'trixie-updates'),
                              ('debian-security', 'trixie-security')]) + '\n')
    lists = output / 'apt-lists'
    (lists / 'partial').mkdir(parents=True, exist_ok=args.resume)
    apt = ['apt-get', '-o', 'Dir::Etc::sourcelist=' + str(apt_sources),
        '-o', 'Dir::Etc::sourceparts=-', '-o', 'Dir::State::Lists=' + str(lists),
        '-o', 'Acquire::ForceIPv4=true', '-o', 'Acquire::http::Timeout=30',
        '-o', 'Acquire::Retries=2', '-o', 'APT::Update::Error-Mode=any',
        '-o', 'APT::Get::AllowUnauthenticated=false']
    subprocess.run([*apt, 'update'], check=True)
    for name, version in sorted(wanted):
        if (name, version) in available:
            row = available[name, version]
            for file in row['files']:
                path = sources / file['path']
                if path.is_symlink() or not path.resolve().is_relative_to(sources):
                    raise ValueError('invalid recorded Linux source path')
                if path.stat().st_size != file['size'] or digest(path) != file['sha256']:
                    raise ValueError('original Linux source changed')
            report['already_in_base'].append({'name': name, 'version': version})
            save()
            continue
        if shutil.disk_usage(output).free < 4 * 1024**3:
            raise ValueError('less than 4 GiB free in builder')
        target = output / 'packages' / name / version.replace(':', '%3a')
        target.mkdir(parents=True, exist_ok=args.resume)
        apt_user = pwd.getpwnam('_apt')
        os.chown(target, apt_user.pw_uid, apt_user.pw_gid)
        fetched = subprocess.run([*apt, '--download-only', '--only-source', 'source', name + '=' + version],
            cwd=target, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env={**os.environ, 'LC_ALL': 'C'})
        print(fetched.stdout, end='', flush=True)
        provenance = 'signed APT snapshot'
        if fetched.returncode:
            if 'Can not find version' not in fetched.stdout and 'Unable to find a source package' not in fetched.stdout:
                fetched.check_returncode()
            collector.historical_download(target, name, version)
            provenance = 'historical Debian snapshot HTTPS and DSC SHA-256; archive signature not verified by this retrieval'
        collector.verify_source_archives(target, name, version)
        files = []
        for path in sorted(target.iterdir()):
            if not path.is_file() or path.is_symlink():
                raise ValueError('unexpected source output')
            files.append({'path': str(path.relative_to(output)), 'size': path.stat().st_size,
                          'sha256': digest(path)})
        report['sources'].append({'name': name, 'version': version, 'files': files, 'provenance': provenance})
        save()
    report['result'] = 'pass'
    save()


if __name__ == '__main__':
    main()
