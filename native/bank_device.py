# SPDX-License-Identifier: BSD-3-Clause
"""Explicit GPT/ext4 installer selection and current mounted-device verification."""
import array
import fcntl
import grp
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from root_bank import mount_identity
from root_freeze import filesystem
from storage_bootstrap import DIRECTORY, protected_file, root_directory, unique

PLAN = '/etc/niaos/root-bank-device.json'
DROPIN = '/etc/systemd/system/var-lib-niaos-roots.mount.d/50-device.conf'
BANK = '/var/lib/niaos/roots'
UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def selection():
    raw = protected_file(PLAN, mode=0o600, limit=4096)
    value = json.loads(raw, object_pairs_hook=unique)
    if (type(value) is not dict or set(value) != {'version', 'partition_uuid', 'filesystem_uuid', 'size_bytes'}
            or type(value['version']) is not int or value['version'] != 1
            or any(type(value[n]) is not str or not UUID.fullmatch(value[n]) or value[n] == '00000000-0000-0000-0000-000000000000'
                   for n in ('partition_uuid', 'filesystem_uuid'))
            or type(value['size_bytes']) is not int or not 32*1024**2 <= value['size_bytes'] <= 2**63-1):
        raise ValueError('bank-device-selection')
    return value, raw


def device_path(plan):
    return '/dev/disk/by-partuuid/' + plan['partition_uuid']


def mount_configuration(plan):
    # UUID syntax is validated before unit generation; no arbitrary unit text.
    return ('# SPDX-License-Identifier: BSD-3-Clause\n[Mount]\nWhat=' + device_path(plan)
            + '\nType=ext4\nOptions=ro,nodev,nosuid,noexec\n').encode('ascii')


def open_device(plan, *, fresh=False):
    parent = root_directory('/dev/disk/by-partuuid')
    try:
        # This one udev-managed symlink is intentional; the opened block FD is
        # probed directly. A symlink name alone is never device authentication.
        fd = os.open(plan['partition_uuid'], os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=parent)
    finally:
        os.close(parent)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISBLK(info.st_mode) or info.st_uid or info.st_mode & 0o002
                or (info.st_mode & 0o020 and info.st_gid not in (0, grp.getgrnam('disk').gr_gid))):
            raise ValueError('bank-block-device')
        dev = f'{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}'
        if not Path('/sys/dev/block', dev, 'partition').is_file():
            raise ValueError('bank-partition-required')
        size = array.array('Q', [0]); fcntl.ioctl(fd, 0x80081272, size, True)  # BLKGETSIZE64, Linux amd64
        if size[0] != plan['size_bytes'] or info.st_rdev == os.stat('/').st_dev:
            raise ValueError('bank-size-or-active-root')
        result = subprocess.run(['/usr/sbin/blkid', '--probe', '--output', 'export', f'/proc/self/fd/{fd}'],
            pass_fds=(fd,), stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=30,
            env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C.UTF-8'})
        if len(result.stdout) > 4096 or len(result.stderr) > 4096:
            raise ValueError('device-probe-size')
        tags = unique(line.split('=', 1) for line in result.stdout.decode('ascii').splitlines())
        expected = {'TYPE': 'ext4', 'USAGE': 'filesystem', 'UUID': plan['filesystem_uuid'],
                    'PART_ENTRY_SCHEME': 'gpt', 'PART_ENTRY_UUID': plan['partition_uuid']}
        if any(tags.get(n) != v for n, v in expected.items()):
            raise ValueError('bank-device-identifiers')
        if fresh:
            with open('/proc/self/mountinfo', 'rb') as stream:
                mounts = stream.read(1024**2 + 1)
            if len(mounts) > 1024**2 or any(line.split()[2] == dev.encode() for line in mounts.splitlines()):
                raise ValueError('bank-device-already-mounted')
        # Ensure udev selection still resolves to the held device after probing.
        if os.stat(device_path(plan)).st_rdev != info.st_rdev:
            raise ValueError('bank-device-selection-changed')
        return fd
    except BaseException:
        os.close(fd)
        raise


def mounted(fd):
    bank = root_directory(BANK)
    try:
        info = os.fstat(bank)
        if info.st_dev != os.fstat(fd).st_rdev:
            raise ValueError('bank-mounted-device-mismatch')
        expected = dict(mount_id=mount_identity(bank), inode=info.st_ino,
                        device_major=os.major(info.st_dev), device_minor=os.minor(info.st_dev))
        actual, readonly = filesystem(bank, expected)
        return actual, readonly
    finally:
        os.close(bank)


def install_mount(plan):
    parent = root_directory('/etc/systemd/system')
    try:
        name = Path(DROPIN).parent.name
        # Existing overrides are never merged, replaced, or silently adopted.
        os.mkdir(name, 0o755, dir_fd=parent)
        directory = os.open(name, DIRECTORY, dir_fd=parent)
        try:
            os.fchmod(directory, 0o755)
            fd = os.open('50-device.conf', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o644, dir_fd=directory)
            try:
                raw = mount_configuration(plan)
                with os.fdopen(fd, 'wb', closefd=False) as stream:
                    stream.write(raw); stream.flush()
                os.fchmod(fd, 0o644); os.fsync(fd)
            finally:
                os.close(fd)
            os.fsync(directory); os.fsync(parent)
        finally:
            os.close(directory)
    finally:
        os.close(parent)


def verify_mount_configuration(plan):
    if protected_file(DROPIN, mode=0o644, limit=4096) != mount_configuration(plan):
        raise ValueError('bank-mount-configuration-changed')
