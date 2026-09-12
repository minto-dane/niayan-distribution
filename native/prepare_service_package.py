#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Export exact internal service sources into a new Debian source directory."""
import argparse
import hashlib
import json
from pathlib import Path
import stat


def prepare(destination, component='root-preparation'):
    distribution = Path(__file__).resolve().parents[1]
    if component not in ('root-preparation', 'archive-observer', 'management'):
        raise ValueError('unknown internal service component')
    packaging = distribution / 'packaging' / component
    files = [(p, p.relative_to(packaging)) for p in sorted(packaging.rglob('*')) if not p.is_dir()]
    inputs = ('native/root_bank.py', 'native/root_freeze.py', 'native/bank_device.py', 'native/root_session.py', 'native/root_session_worker.py', 'native/root_worker_monitor.py', 'native/storage_bootstrap.py', 'native/supply_initialize.py', 'native/operator_guard.py', 'native/root_handoff.py', 'native/root_session_client.py', 'native/root_supervisor.py', 'native/worker/root_extract.c',
              'native/worker/tar_clocks.c', 'native/worker/tar_clocks.h',
              'native/worker/check_tar_clocks.c', 'native/worker/check_tar_clocks.py', 'native/worker/Makefile')
    if component == 'archive-observer':
        inputs = tuple('native/'+name+'.py' for name in ('archive_observer', 'archive_observer_client',
            'archive_credential', 'archive_receipt', 'archive_intake', 'repository'))
        inputs += tuple('tools/'+name+'.py' for name in ('nia_common', 'debian_archive_auth',
            'deb_archive', 'debian_semantics', 'debian_triggers'))
    if component == 'management':
        inputs = tuple('native/' + name + '.py' for name in (
            'package_cli', 'i18n', 'diagnostics', 'media', 'interim_commands',
            'interim_package', 'interim_download', 'interim_intake', 'repository'))
        inputs += tuple('tools/' + name + '.py' for name in (
            'nia_common', 'deb_archive', 'debian_semantics', 'debian_triggers', 'zstd_bounded'))
        inputs += tuple('native/bin/' + name for name in (
            'installp', 'lslpp', 'lppchk', 'install_all_updates', 'instfix', 'inutoc',
            'geninstall', 'suma', 'lppmgr', 'epkg', 'emgr', 'emgr_download_ifix'))
        inputs += tuple(str(path.relative_to(distribution)) for path in
                        sorted((distribution / 'native/locale').glob('*/LC_MESSAGES/*.mo')))
        inputs += ('LICENSE', 'LICENSING.md', 'LICENSES/MIT-legacy.txt')
    files += [(distribution / name, Path(name)) for name in inputs]
    # Review all inputs before creating a fresh output. No upstream patching,
    # recursive workspace export, installed-state discovery or hidden download.
    checked = []
    for source, relative in files:
        info = source.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 1024 * 1024:
            raise ValueError('source is not a bounded regular file: ' + str(relative))
        checked.append((source, relative, source.read_bytes(), 0o755 if info.st_mode & 0o111 else 0o644))
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    manifest = {}
    for source, relative, raw, mode in checked:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw); target.chmod(mode)
        manifest[str(relative)] = {'source': str(source.relative_to(distribution)),
                                  'sha256': hashlib.sha256(raw).hexdigest(), 'mode': mode}
    (destination / 'source-inputs.json').write_text(json.dumps({'format': 1, 'files': manifest}, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--component', choices=('root-preparation', 'archive-observer', 'management'), default='root-preparation')
    args = parser.parse_args()
    prepare(args.output, args.component)
