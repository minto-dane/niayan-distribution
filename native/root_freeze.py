# SPDX-License-Identifier: BSD-3-Clause
"""Privileged controller primitive for a dedicated ext4 root bank.

No public command or implicit service capability upgrade. The independent
controller owns the Bank and mount/device exclusion through this object's Close.
Close and all failure paths leave any successful read-only transition in place.
"""
import ctypes
import os
import time

from root_bank import Rejected, identity, mount_identity, private_directory, protected_mount, read_record, validate_request, FIELDS

DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
MAX_MOUNTS = 1024 * 1024


def clock_check(deadline):
    remaining = deadline - time.clock_gettime(time.CLOCK_BOOTTIME) * 1000
    if not 0 < remaining <= 600000:
        raise Rejected('freeze-deadline')


def filesystem(fd, expected):
    """Match the explicit controller selection to a whole dedicated mount."""
    private_directory(fd)
    protected_mount(fd)
    info = os.fstat(fd)
    actual = {'mount_id': mount_identity(fd), 'inode': info.st_ino,
              'device_major': os.major(info.st_dev), 'device_minor': os.minor(info.st_dev)}
    if (type(expected) is not dict or set(expected) != set(actual)
            or any(type(expected[n]) is not int or expected[n] != value for n, value in actual.items())
            or info.st_ino != 2 or info.st_dev == os.stat('/').st_dev):
        raise Rejected('dedicated-bank-identity')
    # Kernel-owned mount graph, bounded and independently tied to the held FD.
    with open('/proc/self/mountinfo', 'rb') as source:
        raw = source.read(MAX_MOUNTS + 1)
    if len(raw) > MAX_MOUNTS:
        raise Rejected('mount-table-size')
    selected = []
    children = False
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) < 10 or b'-' not in fields:
            raise Rejected('mount-table-format')
        separator = fields.index(b'-')
        if separator < 6 or len(fields) != separator + 4:
            raise Rejected('mount-table-format')
        if fields[1] == str(actual['mount_id']).encode():
            children = True
        if fields[0] == str(actual['mount_id']).encode():
            selected.append((fields, separator))
    if len(selected) != 1 or children:
        raise Rejected('bank-mount-children-or-identity')
    fields, separator = selected[0]
    device = f"{actual['device_major']}:{actual['device_minor']}".encode()
    if fields[2] != device or fields[3] != b'/' or fields[separator + 1] != b'ext4':
        raise Rejected('dedicated-ext4-bank-required')
    mount_options = set(fields[5].split(b','))
    super_options = set(fields[separator + 3].split(b','))
    allowed = {b'ro', b'rw', b'nodev', b'nosuid', b'noexec', b'noatime', b'nodiratime', b'relatime', b'strictatime'}
    if mount_options - allowed or super_options & {b'sync', b'dirsync', b'mand', b'lazytime'}:
        raise Rejected('unsupported-bank-mount-flags')
    # Atime flags are preserved by MS_REMOUNT when none are supplied. Reject
    # other changeable flag profiles rather than silently clearing them.
    return actual, b'ro' in super_options


def readonly_filesystem(fd):
    # MS_REMOUNT without MS_BIND changes the superblock, including other views.
    # The kernel refuses outstanding writable files/mappings; no forced freeze,
    # remount,rw fallback, sysrq, filesystem repair, or automatic thaw is used.
    libc = ctypes.CDLL(None, use_errno=True)
    mount = libc.mount
    mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_void_p]
    mount.restype = ctypes.c_int
    flags = 32 | 1 | 2 | 4 | 8  # REMOUNT, RDONLY, NOSUID, NODEV, NOEXEC
    if mount(None, f'/proc/self/fd/{fd}'.encode(), None, flags, None) != 0:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))


class FrozenRoot:
    """Borrowed Bank and external mount/device authority; own only sampled FDs.

    This is current physical exclusion, not supply/admission or boot authority.
    The caller independently authorizes the selected bank, generation and worker,
    retains the Bank reservation and excludes privileged remount/raw-device
    writers until after Close, and supplies the actual native CAS lease each time.
    """
    def __init__(self):
        self.parent = self.target = -1
        self.bank = None
        self.expected_bank = self.root_identity = self.request = self.records = None
        self.original_deadline = 0
        self.deadline = 0
        self.ready = False

    def acquire(self, bank, request, archive_fd, lease_fd, expected_bank):
        if self.parent >= 0 or self.target >= 0 or self.ready:
            raise Rejected('freeze-handle-in-use')
        if os.getuid() or os.geteuid():
            raise Rejected('freeze-privilege')
        validate_request(request)
        clock_check(request['deadline_ms'])
        bank.check_inputs(request, archive_fd, lease_fd)
        filesystem(bank.directory, expected_bank)
        result = bank.inspect(request['stage'])
        if result['state'] != 'extracted' or result['worker_sha256'] != bank.worker_hash:
            raise Rejected('freeze-extracted-worker')
        try:
            self.parent = os.open(request['stage'], DIRECTORY, dir_fd=bank.directory)
            private_directory(self.parent)
            intent = read_record(self.parent, 'intent.json')
            if any(intent[n] != request[n] for n in FIELDS - {'deadline_ms'}):
                raise Rejected('freeze-intent-binding')
            self.target = os.open('root', DIRECTORY, dir_fd=self.parent)
            target_info = os.fstat(self.target)
            if target_info.st_dev != os.fstat(bank.directory).st_dev or mount_identity(self.target) != expected_bank['mount_id']:
                raise Rejected('freeze-root-mount')
            self.bank = bank
            self.expected_bank = dict(expected_bank)
            self.request = dict(request)
            self.records = (intent, result)
            self.original_deadline = intent['deadline_ms']
            self.deadline = request['deadline_ms']
            self.root_identity = dict(expected_bank, inode=target_info.st_ino)
            clock_check(self.deadline)
            readonly_filesystem(bank.directory)
            # Once the syscall succeeds, all later errors leave storage read-only.
            self.ready = True
            self.observe(archive_fd, lease_fd)
        except BaseException:
            self.close()
            raise

    def observe(self, archive_fd, lease_fd):
        if not self.ready or self.bank is None:
            raise Rejected('freeze-not-held')
        clock_check(self.deadline)
        bank = self.bank
        bank.check_inputs(self.request, archive_fd, lease_fd)
        _, readonly = filesystem(bank.directory, self.expected_bank)
        if not readonly or not os.fstatvfs(self.target).f_flag & os.ST_RDONLY:
            raise Rejected('bank-not-filesystem-readonly')
        current_parent = os.open(self.request['stage'], DIRECTORY, dir_fd=bank.directory)
        try:
            if identity(os.fstat(current_parent)) != identity(os.fstat(self.parent)):
                raise Rejected('frozen-stage-changed')
            current = os.open('root', DIRECTORY, dir_fd=current_parent)
            try:
                if (identity(os.fstat(current)) != identity(os.fstat(self.target))
                        or mount_identity(current) != self.root_identity['mount_id']):
                    raise Rejected('frozen-root-changed')
                protected_mount(current)
            finally:
                os.close(current)
        finally:
            os.close(current_parent)
        if (read_record(self.parent, 'intent.json'), bank.inspect(self.request['stage'])) != self.records:
            raise Rejected('frozen-record-changed')
        clock_check(self.deadline)
        return {'original_deadline_ms': self.original_deadline, 'root': dict(self.root_identity)}

    def close(self):
        self.ready = False
        for name in ('target', 'parent'):
            fd = getattr(self, name)
            if fd >= 0:
                os.close(fd)
                setattr(self, name, -1)
        self.bank = None
        self.expected_bank = self.root_identity = self.request = self.records = None
        self.original_deadline = self.deadline = 0
