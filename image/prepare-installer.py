#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Add unmodified Debian installer packages through live-build's local inputs."""
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile


def main():
    if os.getuid() != 0:
        raise ValueError('run inside the disposable root builder')
    build = Path('/build')
    lock = json.loads((build / 'input-manifest.json').read_text())['lock']
    destination = build / 'live/config/packages.binary'
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='nia-installer-apt-') as temporary:
        top = Path(temporary)
        top.chmod(0o755)
        (top / 'lists/partial').mkdir(parents=True)
        downloads = top / 'downloads'
        downloads.mkdir()
        apt_user = pwd.getpwnam('_apt')
        os.chown(downloads, apt_user.pw_uid, apt_user.pw_gid)
        sources = top / 'sources.list'
        sources.write_text(
            'deb [check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] '
            f'http://snapshot.debian.org/archive/debian/{lock["snapshot"]}/ '
            f'{lock["distribution"]} main/debian-installer\n')
        apt = ['apt-get', '-o', 'Dir::Etc::sourcelist=' + str(sources),
               '-o', 'Dir::Etc::sourceparts=-', '-o', 'Dir::State::Lists=' + str(top / 'lists'),
               '-o', 'Acquire::ForceIPv4=true', '-o', 'Acquire::http::Timeout=30',
               '-o', 'Acquire::Retries=2', '-o', 'APT::Update::Error-Mode=any',
               '-o', 'APT::Get::AllowUnauthenticated=false']
        subprocess.run([*apt, 'update'], check=True)
        for name, version in sorted(lock['installer_packages'].items()):
            # APT authenticates the index and verifies the downloaded binary hash.
            subprocess.run([*apt, 'download', name + '=' + version],
                           cwd=downloads, check=True)
            candidates = list(downloads.glob(name + '_*.udeb'))
            if len(candidates) != 1:
                raise ValueError('unexpected installer package inventory: ' + name)
            actual = subprocess.check_output(['dpkg-deb', '-f', str(candidates[0]),
                                              'Version'], text=True).strip()
            if actual != version:
                raise ValueError('installer package version mismatch: ' + name)
            shutil.copyfile(candidates[0], destination / candidates[0].name)


if __name__ == '__main__':
    main()
