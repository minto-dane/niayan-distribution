# SPDX-License-Identifier: MIT
"""Actual public CLI, system CA trust and fixed policy in a disposable container.

Run only in native/Containerfile's private test image as root with network=none.
Test trust and policy are confined to that container's writable layer.
"""
import os
from pathlib import Path
import shutil
import subprocess
import time

from interim_package import encode
from nia_common import canonical, sha
from test_interim_package import fixture
from test_repository_https import HTTPSTests


def main():
    policy_dir = Path('/etc/nia')
    ca = Path('/usr/local/share/ca-certificates/nia-download-test.crt')
    if (os.geteuid() != 0 or not Path('/usr/share/nia-test-packages.txt').is_file()
            or not any(Path(p).is_file() for p in ('/.dockerenv', '/run/.containerenv'))
            or policy_dir.exists() or policy_dir.is_symlink() or ca.exists() or ca.is_symlink()):
        raise RuntimeError('requires a fresh disposable native test container as root')
    case = HTTPSTests()
    case.setUp()
    try:
        shutil.copyfile(case.certificate, ca)
        subprocess.run(['/usr/sbin/update-ca-certificates'], check=True, timeout=30,
                       stdout=subprocess.DEVNULL)
        manifest, debs = fixture()
        manifest.update(created_at=int(time.time())-60, expires_at=int(time.time())+300, security_epoch=4)
        raw = encode(manifest, debs)
        target = 'fixes/fix001.epkg'
        case.remote.delegated[target] = raw
        for kind, data in (('contracts/rollback', b'rollback contract reference, not authenticated'),
                           ('contracts/effects', b'effect contract reference, not authenticated'),
                           ('sources', b'base source reference'), ('sources', b'target source reference')):
            case.remote.targets[kind + '/' + sha(data) + '.json'] = data
        case.remote.publish()
        policy_dir.mkdir(mode=0o755)
        policy = policy_dir / 'repository.json'
        policy.write_bytes(canonical(dict(schema='org.niaos.repository-policy/v1',
            cache=str(case.cache), bootstrap_sha256=sha(case.remote.bootstrap),
            metadata_url=case.remote.metadata_url, targets_url=case.remote.targets_url, security_epoch=4)))
        policy.chmod(0o644)
        command = str(Path(__file__).resolve().parent / 'bin/emgr_download_ifix')
        output = case.directory / 'output'

        def invoke(directory, language='C.UTF-8'):
            return subprocess.run([command, '-L', case.remote.targets_url+target, '-P', str(directory)],
                env={'PATH': '', 'LANG': language, 'LC_ALL': language, 'HOME': '/tmp'},
                capture_output=True, encoding='utf-8', timeout=30)

        result = invoke(output)
        destination = output / 'fix001.epkg'
        if (result.returncode != 0 or result.stderr
                or result.stdout != 'Downloaded interim fix: ' + str(destination) + '\n'
                or destination.read_bytes() != raw):
            raise AssertionError(('public authenticated download', result))
        print('PASS public command: real HTTPS, system CA, fixed root policy, delegated signatures and exact bytes')
        localized = case.directory / '日本語'
        result = invoke(localized, 'ja_JP.UTF-8')
        if (result.returncode != 0 or result.stderr
                or result.stdout != '緊急修正を取得しました: ' + str(localized / 'fix001.epkg') + '\n'
                or (localized / 'fix001.epkg').read_bytes() != raw):
            raise AssertionError(('Japanese public download', result))
        print('PASS public command: Japanese response and Unicode output path preserve the original artifact')
        result = invoke(output)
        if result.returncode != 1 or result.stdout or destination.read_bytes() != raw:
            raise AssertionError(('exclusive output', result))
        print('PASS public command: existing output retained and failure reported')
        name = next(p for p in case.remote.targets if p.startswith('contracts/effects/'))
        case.remote.targets[name] = b'wrong reference with valid publisher signature'
        case.remote.version += 1
        case.remote.publish()
        rejected = case.directory / 'rejected'
        result = invoke(rejected)
        if result.returncode != 1 or result.stdout or rejected.exists() or 'reference differs' not in result.stderr:
            raise AssertionError(('reference binding', result))
        print('PASS public command: authenticated but incorrectly bound reference creates no output')
        result = invoke(rejected, 'ja_JP.UTF-8')
        if (result.returncode != 1 or result.stdout or rejected.exists()
                or '[NIA-E-REFERENCE]' not in result.stderr or '一致しません' not in result.stderr):
            raise AssertionError(('Japanese reference rejection', result))
        print('PASS public command: Japanese authentication failure retains the same diagnostic code and no output')
        policy.chmod(0o666)
        result = invoke(rejected)
        if result.returncode != 1 or result.stdout or rejected.exists() or 'Traceback' in result.stderr:
            raise AssertionError(('untrusted policy permissions', result))
        print('PASS public command: writable policy rejected without traceback or output')
    finally:
        case.tearDown()
        if policy_dir.is_dir():
            (policy_dir / 'repository.json').unlink(missing_ok=True)
            policy_dir.rmdir()
        ca.unlink(missing_ok=True)
        subprocess.run(['/usr/sbin/update-ca-certificates'], check=True, timeout=30,
                       stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
