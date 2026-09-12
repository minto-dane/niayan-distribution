#!/usr/bin/python3 -I
# SPDX-License-Identifier: BSD-3-Clause
"""Explicit first provisioning of administrator-selected public supply inputs.

No keys, policy, floor or execution authority are invented. Native verification
runs as nia-pkg. This tool is neither an updater nor automatic startup repair.
"""
from enum import Enum, auto
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import tempfile

BASE = '/var/lib/niaos'
CONFIG = '/etc/niaos'
OBSERVER = '/usr/libexec/nia/pkg_supply_observe'
ATTEMPT = 'supply-initialization.json'
COMPLETE = 'supply-initialization-complete.json'
DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
POLICY_LIMIT = 56 + 80 * 256


class Rejected(ValueError):
    pass


class Phase(Enum):
    NEW = auto()
    RECORDED = auto()
    STAGED = auto()
    VERIFIED = auto()
    POLICY = auto()
    FLOOR = auto()
    COMPLETE = auto()
    FAILED = auto()


def advance(before: Phase, after: Phase) -> Phase:
    if after is Phase.FAILED and before not in (Phase.COMPLETE, Phase.FAILED):
        return after
    order: tuple[Phase, ...] = (Phase.NEW, Phase.RECORDED, Phase.STAGED, Phase.VERIFIED,
                               Phase.POLICY, Phase.FLOOR, Phase.COMPLETE)
    if before not in order[:-1] or order[order.index(before) + 1] is not after:
        raise Rejected('supply-initialization-order')
    return after


def directory(path: str) -> int:
    if (not path.startswith('/') or len(path) > 4096 or path.count('/') > 128
            or any(part in ('.', '..') for part in path.split('/'))):
        raise Rejected('absolute-protected-path-required')
    fd = os.open('/', DIRECTORY)
    try:
        initial = os.fstat(fd)
        if initial.st_uid != 0 or stat.S_IMODE(initial.st_mode) & 0o022:
            raise Rejected('unprotected-directory')
        for part in Path(path).parts[1:]:
            child = os.open(part, DIRECTORY, dir_fd=fd)
            previous = fd
            fd = child
            os.close(previous)
            info = os.fstat(fd)
            if info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
                raise Rejected('unprotected-directory')
        return fd
    except BaseException:
        os.close(fd)
        raise


def open_input(path: str) -> int:
    if not path.startswith('/') or len(path) > 4096:
        raise Rejected('bounded-absolute-input-path-required')
    parent = directory(str(Path(path).parent))
    fd = -1
    try:
        fd = os.open(Path(path).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                     dir_fd=parent)
    finally:
        try:
            os.close(parent)
        except BaseException:
            if fd >= 0:
                os.close(fd)
            raise
    return fd


def protected(path: str, limit: int) -> bytes:
    fd = open_input(path)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != 0 or before.st_nlink != 1
                or before.st_mode & 0o022 or not 0 < before.st_size <= limit):
            raise Rejected('unprotected-or-oversize-input')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(limit + 1)
        after = os.fstat(fd)
        def identity(info: os.stat_result) -> tuple[int, ...]:
            return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_uid,
                    info.st_gid, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if len(raw) != before.st_size or identity(after) != identity(before):
            raise Rejected('input-changed')
        return raw
    finally:
        os.close(fd)


def create(parent: int, name: str, raw: bytes, mode: int) -> None:
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                 mode, dir_fd=parent)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(raw)
            stream.flush()
        os.fchmod(fd, mode)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(parent)


def publish(source: int, destination: int, name: str) -> None:
    # link is no-replace. While both links exist, the native reader rejects the
    # file. A failed/unconfirmed unlink is not repaired or retried automatically.
    os.link(name, name, src_dir_fd=source, dst_dir_fd=destination, follow_symlinks=False)
    os.fsync(destination)
    os.unlink(name, dir_fd=source)
    os.fsync(source)
    os.fsync(destination)


def verify(policy: str, floor: str, root: str, request: str) -> None:
    account = pwd.getpwnam('nia-pkg')
    if account.pw_uid <= 0 or account.pw_gid <= 0:
        raise Rejected('nonroot-provider-account-required')
    executable = open_input(OBSERVER)
    try:
        info = os.fstat(executable)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
                or info.st_mode & 0o6022 or not info.st_mode & 0o111
                or os.read(executable, 4) != b'\x7fELF'):
            raise Rejected('protected-native-observer-required')
        # prlimit execs the pinned reader, with bounded output files/CPU. The
        # reader has no package effects and its own five-second BOOTTIME limit.
        with tempfile.TemporaryFile(dir=BASE) as output, tempfile.TemporaryFile(dir=BASE) as error:
            result = subprocess.run(['/usr/bin/prlimit', '--fsize=65536:65536', '--cpu=5:5', '--',
                f'/proc/self/fd/{executable}', '--planning', policy, floor, root, request],
                pass_fds=(executable,), user=account.pw_uid, group=account.pw_gid, extra_groups=[],
                stdin=subprocess.DEVNULL, stdout=output, stderr=error, timeout=8,
                env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'})
            output.seek(0)
            error.seek(0)
            raw = output.read(65537)
            if (result.returncode or error.read(1) or len(raw) > 65536
                    or not raw.startswith(b'format=nia-site-supply-1\nstatus=OK\nplanning=true\nmap=' + b'0'*64 + b'\n')
                    or not raw.endswith(b'execution_permit=false\n')):
                raise Rejected('native-supply-observation-refused')
    finally:
        os.close(executable)


def initialize(policy_input: str, floor_input: str, root: str, request: str) -> None:
    if os.getuid() or os.geteuid():
        raise Rejected('installer-root-required')
    for identity in (root, request):
        if re.fullmatch('[0-9a-f]{32}', identity) is None or identity == '0'*32:
            raise Rejected('independent-root-and-request-required')
    policy = protected(policy_input, POLICY_LIMIT)
    floor = protected(floor_input, 72)
    phase = Phase.NEW
    owned: list[int] = []
    try:
        base = directory(BASE)
        owned.append(base)
        config = directory(CONFIG)
        owned.append(config)
        for parent, name in ((base, ATTEMPT), (base, COMPLETE), (base, 'trust'), (config, 'supply')):
            try:
                os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise Rejected('existing-supply-state-requires-recovery-or-managed-update')
        context: dict[str, str | int | bool] = dict(version=1, root_id=root, request_id=request,
            policy_sha256=hashlib.sha256(policy).hexdigest(), floor_sha256=hashlib.sha256(floor).hexdigest(),
            execution_permit=False)
        raw = (json.dumps(context, sort_keys=True, separators=(',', ':'))+'\n').encode('ascii')
        create(base, ATTEMPT, raw, 0o600)
        phase = advance(phase, Phase.RECORDED)
        for parent, name in ((config, 'supply'), (base, 'trust')):
            os.mkdir(name, 0o755, dir_fd=parent)
            child = os.open(name, DIRECTORY, dir_fd=parent)
            owned.append(child)
            os.fchmod(child, 0o755)
            os.fsync(child)
            os.fsync(parent)
        policy_dir, floor_dir = owned[-2:]
        # Staging directories keep the native reader's fixed filenames. They
        # are retained on failure; no initialization path erases recovery data.
        for parent in (policy_dir, floor_dir):
            os.mkdir('pending', 0o755, dir_fd=parent)
            child = os.open('pending', DIRECTORY, dir_fd=parent)
            owned.append(child)
            os.fchmod(child, 0o755)
            os.fsync(parent)
        staged_policy, staged_floor = owned[-2:]
        create(staged_policy, 'supply.bin', policy, 0o444)
        create(staged_floor, 'supply.floor', floor, 0o444)
        phase = advance(phase, Phase.STAGED)
        verify(CONFIG+'/supply/pending', BASE+'/trust/pending', root, request)
        phase = advance(phase, Phase.VERIFIED)
        publish(staged_policy, policy_dir, 'supply.bin')
        phase = advance(phase, Phase.POLICY)
        publish(staged_floor, floor_dir, 'supply.floor')
        phase = advance(phase, Phase.FLOOR)
        verify(CONFIG+'/supply', BASE+'/trust', root, request)
        # Readiness is reported only after native reobservation and durable
        # completion. A failure after floor publication may already be visible;
        # it is indeterminate, never rollback or permission to initialize again.
        create(base, COMPLETE, raw, 0o600)
        phase = advance(phase, Phase.COMPLETE)
    except BaseException:
        phase = advance(phase, Phase.FAILED)
        raise
    finally:
        errors: list[OSError] = []
        for fd in reversed(owned):
            try:
                os.close(fd)
            except OSError as error:
                errors.append(error)
        if errors:
            raise Rejected('supply-initialization-close-indeterminate') from errors[0]


def main() -> None:
    if len(sys.argv) != 6 or sys.argv[1] != '--initialize':
        raise Rejected('usage: supply_initialize.py --initialize POLICY FLOOR ROOT_ID REQUEST_ID')
    initialize(*sys.argv[2:])
    print('format=nia-supply-initialization-1\nstatus=OK\nexecution_permit=false')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as failure:
        print('status=REFUSED_OR_INDETERMINATE\n'+str(failure), file=sys.stderr)
        raise SystemExit(2) from failure
