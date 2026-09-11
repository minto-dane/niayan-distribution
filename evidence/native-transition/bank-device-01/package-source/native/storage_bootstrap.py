#!/usr/bin/python3 -I
# SPDX-License-Identifier: BSD-3-Clause
"""Explicit internal installer action for fresh native storage, never startup repair."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import resource
import stat
import subprocess
import sys

# -I excludes sibling modules; add only this protected installed code directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

BASE = '/var/lib/niaos'
POLICY = '/etc/niaos/root-preparation.json'
INITIALIZER = '/usr/libexec/nia/pkg_store_bootstrap'
BANK_TOOL = '/usr/libexec/niaos/root_bank.py'
WORKER = '/usr/libexec/niaos/root-extract'
MOUNT = 'var-lib-niaos-roots.mount'
ENV = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'}
DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def root_directory(path):
    """Walk only root-owned, non-writable-by-others directories without symlinks."""
    fd = os.open('/', DIRECTORY)
    try:
        for part in Path(path).parts[1:]:
            child = os.open(part, DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            if info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
                raise ValueError('unprotected-parent')
        return fd
    except BaseException:
        os.close(fd)
        raise


def protected_file(path, *, mode=None, executable=False, limit=32 * 1024 * 1024):
    parent = root_directory(str(Path(path).parent))
    try:
        fd = os.open(Path(path).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                     dir_fd=parent)
    finally:
        os.close(parent)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
                or info.st_mode & 0o022 or info.st_size > limit
                or (mode is not None and stat.S_IMODE(info.st_mode) != mode)
                or (executable and (not info.st_mode & 0o111 or info.st_mode & 0o6000))):
            raise ValueError('unprotected-input')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('input-size')
        return raw
    finally:
        os.close(fd)


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate-policy-field')
        value[key] = item
    return value


def record(parent, name, value):
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                 0o600, dir_fd=parent)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(raw)
            stream.flush()
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(parent)


def new_directory(parent, name, uid, gid):
    os.mkdir(name, 0o700, dir_fd=parent)
    fd = os.open(name, DIRECTORY, dir_fd=parent)
    try:
        os.fchown(fd, uid, gid)
        os.fchmod(fd, 0o700)
        os.fsync(fd)
        os.fsync(parent)
        return fd
    except BaseException:
        os.close(fd)
        raise


def run(*command, **kwargs):
    return subprocess.run(command, stdin=subprocess.DEVNULL, env=ENV, cwd='/',
                          check=True, timeout=60, **kwargs)


def initialize():
    if os.getuid() != 0 or os.geteuid() != 0:
        raise ValueError('requires-root-installer')
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    account = pwd.getpwnam('nia-pkg')
    if account.pw_uid <= 0 or account.pw_gid <= 0 or account.pw_shell != '/usr/sbin/nologin':
        raise ValueError('invalid-core-account')
    raw_policy = protected_file(POLICY, mode=0o600, limit=4096)
    policy = json.loads(raw_policy, object_pairs_hook=unique)
    expected = {'version': 2, 'bank': BASE + '/roots', 'reservation': BASE + '/core/store/store.lock',
                'worker': WORKER, 'client_user': 'nia-pkg'}
    if type(policy) is not dict or policy != expected or type(policy.get('version')) is not int:
        raise ValueError('installer-policy-mismatch')
    native = protected_file(INITIALIZER, executable=True)
    if not native.startswith(b'\x7fELF'):
        raise ValueError('initializer-not-elf')
    protected_file(BANK_TOOL)
    worker = protected_file(WORKER, executable=True)
    for unit in ('niaos-root-preparation.socket', 'niaos-root-preparation.service', MOUNT):
        state = run('/usr/bin/systemctl', 'show', unit, '--property=ActiveState', '--value',
                    capture_output=True).stdout
        if state != b'inactive\n':
            raise ValueError('storage-unit-not-inactive')
        loaded = run('/usr/bin/systemctl', 'show', unit, '--property=LoadState', '--value',
                     capture_output=True).stdout
        if loaded != b'loaded\n':
            raise ValueError('storage-unit-not-loaded')
    import bank_device
    plan, raw_device = bank_device.selection()
    device = bank_device.open_device(plan, fresh=True)
    try:
        initialize_selected(account, raw_policy, native, worker, plan, raw_device, device)
    finally:
        os.close(device)


def initialize_selected(account, raw_policy, native, worker, plan, raw_device, device):
    import bank_device
    from root_freeze import readonly_filesystem
    if Path(bank_device.DROPIN).parent.exists():
        raise ValueError('existing-bank-mount-override')
    parent = root_directory('/var/lib')
    try:
        try:
            os.mkdir('niaos', 0o755, dir_fd=parent)
            # umask is private by default; the parent permits the core to traverse.
            base = os.open('niaos', DIRECTORY, dir_fd=parent)
            os.fchmod(base, 0o755)
            os.fsync(base)
            os.fsync(parent)
        except FileExistsError:
            base = root_directory(BASE)
    finally:
        os.close(parent)
    try:
        info = os.fstat(base)
        if stat.S_IMODE(info.st_mode) != 0o755:
            raise ValueError('storage-parent-mode')
        # Even an empty prior core/bank is not an invitation to initialize it.
        for name in ('core', 'roots', 'bootstrap.json', 'bootstrap-complete.json'):
            try:
                os.stat(name, dir_fd=base, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise ValueError('existing-or-incomplete-storage')
        intent = {'format': 1, 'state': 'initializing', 'uid': account.pw_uid, 'gid': account.pw_gid,
                  'policy_sha256': hashlib.sha256(raw_policy).hexdigest(),
                  'initializer_sha256': hashlib.sha256(native).hexdigest(),
                  'worker_sha256': hashlib.sha256(worker).hexdigest(),
                  'device_plan_sha256': hashlib.sha256(raw_device).hexdigest()}
        # O_EXCL serializes competing installers. Nothing rolls back this intent.
        record(base, 'bootstrap.json', intent)
        core = new_directory(base, 'core', account.pw_uid, account.pw_gid)
        try:
            store = new_directory(core, 'store', account.pw_uid, account.pw_gid)
            os.close(store)
        finally:
            os.close(core)
        bank = new_directory(base, 'roots', 0, 0)
        os.close(bank)
        for operation in ('initialize', 'check'):
            result = run(INITIALIZER, operation, BASE + '/core/store', user=account.pw_uid,
                         group=account.pw_gid, extra_groups=[], capture_output=True)
            if result.stdout != b'format=nia-store-bootstrap-1\nstatus=OK\n':
                raise ValueError('initializer-protocol')
        bank_device.install_mount(plan)
        run('/usr/bin/systemctl', 'daemon-reload')
        run('/usr/bin/systemctl', 'start', MOUNT)
        # The installer exclusively owns this fresh, selected partition. The
        # persistent unit always mounts read-only; only initialization opens RW.
        bank = root_directory(BASE + '/roots')
        try:
            info = os.fstat(bank)
            if info.st_dev != os.fstat(device).st_rdev or info.st_ino != 2:
                raise ValueError('fresh-bank-mounted-device')
            # Never remove recovery contents or an existing bank. An empty
            # mkfs-created lost+found is the sole permitted initial directory.
            names = os.listdir(bank)
            if names not in ([], ['lost+found']):
                raise ValueError('fresh-bank-not-empty')
            if names:
                lost = os.open('lost+found', DIRECTORY, dir_fd=bank)
                try:
                    li = os.fstat(lost)
                    if li.st_uid or li.st_dev != info.st_dev or os.listdir(lost):
                        raise ValueError('fresh-bank-recovery-contents')
                finally:
                    os.close(lost)
            try:
                run('/usr/bin/mount', '-o', 'remount,rw,nodev,nosuid,noexec', BASE + '/roots')
                os.fchmod(bank, 0o700)
                bank_device.mounted(device)
                if names: os.rmdir('lost+found', dir_fd=bank)
                run('/usr/bin/python3', '-I', BANK_TOOL, '--config', POLICY, '--provision-bank')
            finally:
                readonly_filesystem(bank)
            bank_device.verify_mount_configuration(plan)
            _, readonly = bank_device.mounted(device)
            if not readonly: raise ValueError('initialized-bank-not-readonly')
        finally:
            os.close(bank)
        record(base, 'bootstrap-complete.json', {
            'format': 1, 'state': 'storage-initialized', 'uid': account.pw_uid, 'gid': account.pw_gid,
            'intent_sha256': hashlib.sha256((json.dumps(intent, sort_keys=True, separators=(',', ':'))
                                           + '\n').encode('ascii')).hexdigest(),
            'device_plan_sha256': hashlib.sha256(raw_device).hexdigest(),
            'bank_readonly': True,
            'service_activated': False, 'admission_configured': False, 'published': False})
    finally:
        os.close(base)


def check_bank():
    if os.getuid() or os.geteuid(): raise ValueError('requires-root-check')
    import bank_device
    plan, raw = bank_device.selection()
    bank_device.verify_mount_configuration(plan)
    intent_raw = protected_file(BASE + '/bootstrap.json', mode=0o600, limit=4096)
    intent = json.loads(intent_raw, object_pairs_hook=unique)
    complete = json.loads(protected_file(BASE + '/bootstrap-complete.json', mode=0o600, limit=4096), object_pairs_hook=unique)
    digest = hashlib.sha256(raw).hexdigest()
    if (type(intent) is not dict or type(complete) is not dict
            or intent.get('device_plan_sha256') != digest or complete.get('device_plan_sha256') != digest
            or complete.get('intent_sha256') != hashlib.sha256(intent_raw).hexdigest()
            or complete.get('state') != 'storage-initialized' or complete.get('bank_readonly') is not True):
        raise ValueError('bank-initialization-binding')
    device = bank_device.open_device(plan)
    try:
        actual, readonly = bank_device.mounted(device)
        protected_file(BASE + '/roots/bank.json', mode=0o600, limit=4096)
        protected_file(BASE + '/roots/bank.lock', mode=0o600, limit=0)
        return {'format': 1, 'status': 'bank-device-checked', 'identity': actual, 'readonly': readonly}
    finally:
        os.close(device)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--initialize', action='store_true')
    action.add_argument('--check-bank', action='store_true')
    args = parser.parse_args()
    try:
        if args.check_bank:
            print(json.dumps(check_bank(), sort_keys=True)); return 0
        initialize()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        # Stable internal token; public localized management UI owns presentation.
        print(json.dumps({'format': 1, 'status': 'refused-or-incomplete', 'error': type(error).__name__}))
        return 2
    print(json.dumps({'format': 1, 'status': 'storage-initialized', 'service_activated': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
