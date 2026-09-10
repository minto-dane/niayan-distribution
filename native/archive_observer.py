# SPDX-License-Identifier: BSD-3-Clause
"""Internal socket-activated original archive observer, one request per process."""
from __future__ import annotations

import array
import fcntl
import os
from pathlib import Path
import pwd
import socket
import stat
import struct
import sys
import tempfile
import time

# The package places this entry and its dependencies under a root-owned prefix;
# python -I excludes ambient imports. No caller-selected modules or fetchers.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from archive_credential import issue_from_credential
from archive_receipt import scope
from repository import Repository, initialize, base_url, target_path
from nia_common import Invalid, canonical, digest, fields, integer, parse_json, read_file, relative, sha, write_new
from debian_archive_auth import MAX_RELEASE, MAX_INDEX, POCKETS
from deb_archive import MAX_DEB

CONFIG = Path('/etc/niaos/archive-observer.json')
KEYRING = Path('/etc/niaos/archive-keyring.gpg')
BOOTSTRAP_ROOT = Path('/etc/niaos/archive-root.json')
STATE = Path('/var/lib/niaos/supply')
CACHE = STATE/'repository'
SOCKET = '/run/niaos/archive-observer.sock'
MAX_PACKET = 4096
MAX_CONFIG = 65536
MAX_KEYRING = 4*1024*1024
MAX_POLICY = 5*1024*1024
SECONDS = 120
SEALS = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL


def protected(path: Path, limit: int) -> bytes:
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parts[1:-1]:
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = new
            info = os.fstat(fd)
            if info.st_uid != 0 or info.st_mode & 0o022:
                raise Invalid('unprotected observer configuration parent')
        # read_file walks the complete path again without following links and
        # checks the file owner, links and changes during its bounded read.
        return read_file(path, limit, owner=0)
    finally:
        os.close(fd)


def configuration(raw: bytes) -> dict:
    value = parse_json(raw, limit=MAX_CONFIG)
    fields(value, 'schema root_sha256 metadata_url targets_url public_key scopes', 'observer configuration')
    if value['schema'] != 'org.niaos.archive-observer/v1':
        raise Invalid('observer configuration version')
    digest(value['root_sha256']); digest(value['public_key'])
    base_url(value['metadata_url']); base_url(value['targets_url'])
    rows = value['scopes']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 64:
        raise Invalid('observer scope count')
    repository = Repository(CACHE, value['root_sha256'], value['metadata_url'], value['targets_url'])
    names = []
    for row in rows:
        fields(row, 'scope target codename minimum_security_epoch maximum_lifetime_seconds', 'observer scope')
        target_path(row['target']); digest(row['scope'])
        if not isinstance(row['codename'], str) or row['codename'] not in POCKETS:
            raise Invalid('observer archive pocket')
        if scope(repository, row['target']) != row['scope']:
            raise Invalid('observer scope differs from repository identity')
        integer(row['minimum_security_epoch'], 1, 2**53-1, 'observer epoch floor')
        integer(row['maximum_lifetime_seconds'], 1, 3600, 'observer receipt lifetime')
        names.append(row['scope'])
    if names != sorted(set(names)):
        raise Invalid('observer scopes must be unique and sorted')
    return value


def request(raw: bytes) -> dict:
    value = parse_json(raw, limit=MAX_PACKET)
    fields(value, 'schema request_id scope index deb', 'observer request')
    if value['schema'] != 'org.niaos.archive-observer-request/v1' or canonical(value) != raw:
        raise Invalid('observer request version or encoding')
    digest(value['request_id']); digest(value['scope'])
    for name in ('index', 'deb'):
        relative(value[name])
        if len(value[name]) > 1024 or len(value[name].split('/')) > 32:
            raise Invalid('observer input path bound')
    return value


def receive(connection: socket.socket, expected_fds: int) -> tuple[bytes, list[int]]:
    raw, ancillary, flags, _ = connection.recvmsg(MAX_PACKET, socket.CMSG_SPACE(8*4), socket.MSG_CMSG_CLOEXEC)
    fds = []
    try:
        unexpected = False
        for level, kind, data in ancillary:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                values = array.array('i'); values.frombytes(data)
                fds.extend(values)
            else:
                unexpected = True
        if unexpected or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) or len(fds) != expected_fds or not raw:
            raise Invalid('observer packet or descriptor count')
        return raw, fds
    except BaseException:
        for fd in fds:
            os.close(fd)
        raise


def copy_original(fd: int, path: Path, limit: int, deadline: float) -> None:
    before = os.fstat(fd)
    if (not stat.S_ISREG(before.st_mode) or not 1 <= before.st_size <= limit
            or fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY):
        raise Invalid('observer requires bounded read-only original descriptors')
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    offset = 0
    with path.open('xb') as output:
        while offset < before.st_size:
            if time.monotonic() >= deadline:
                raise Invalid('observer copy deadline')
            data = os.pread(fd, min(1024*1024, before.st_size-offset), offset)
            if not data:
                raise Invalid('observer original shortened')
            output.write(data)
            offset += len(data)
    after = os.fstat(fd)
    token = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode, s.st_uid, s.st_gid)
    if token(before) != token(after):
        raise Invalid('observer original changed')


def sealed(raw: bytes) -> int:
    fd = os.memfd_create('nia-observer-result', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        view = memoryview(raw)
        while view:
            count = os.write(fd, view)
            if count <= 0:
                raise OSError('short observer result write')
            view = view[count:]
        os.fchmod(fd, 0o400)
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, SEALS)
        return os.open('/proc/self/fd/'+str(fd), os.O_RDONLY | os.O_CLOEXEC)
    finally:
        os.close(fd)


def handle(connection: socket.socket) -> None:
    descriptors = []
    results = []
    identity = '0'*64
    deadline = time.monotonic()+SECONDS
    connection.settimeout(5)
    stage = 'peer'
    try:
        _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        client_uid = pwd.getpwnam('nia-pkg').pw_uid
        if client_uid == 0 or uid != client_uid or uid == os.geteuid():
            raise Invalid('observer peer')
        stage = 'configuration'
        config_raw = protected(CONFIG, MAX_CONFIG)
        config = configuration(config_raw)
        stage = 'bootstrap-history'
        state_info = os.stat(STATE, follow_symlinks=False)
        if (not stat.S_ISDIR(state_info.st_mode) or state_info.st_uid != os.geteuid()
                or stat.S_IMODE(state_info.st_mode) != 0o700):
            raise Invalid('observer state directory protection')
        intent = read_file(STATE/'bootstrap-intent.json', MAX_PACKET, owner=os.geteuid())
        complete = read_file(STATE/'bootstrap-complete.json', MAX_PACKET, owner=os.geteuid())
        record = parse_json(intent, limit=MAX_PACKET)
        fields(record, 'schema configuration_sha256 root_sha256', 'observer bootstrap history')
        if (intent != complete or canonical(record) != intent
                or record['schema'] != 'org.niaos.archive-observer-bootstrap/v1'
                or record['root_sha256'] != config['root_sha256']):
            raise Invalid('observer bootstrap history')
        digest(record['configuration_sha256'])
        stage = 'request'
        keyring = protected(KEYRING, MAX_KEYRING)
        raw, descriptors = receive(connection, 3)
        job = request(raw)
        identity = job['request_id']
        row = next((r for r in config['scopes'] if r['scope'] == job['scope']), None)
        if row is None:
            raise Invalid('observer scope is not configured')
        stage = 'original-copy'
        with tempfile.TemporaryDirectory(prefix='nia-observer-') as temporary:
            snapshot = Path(temporary)
            destination = snapshot/'dists'/row['codename']
            copy_original(descriptors[0], destination/'InRelease', MAX_RELEASE, deadline)
            copy_original(descriptors[1], destination/job['index'], MAX_INDEX, deadline)
            copy_original(descriptors[2], snapshot/job['deb'], MAX_DEB, deadline)
            stage = 'credential'
            credential = Path(os.environ['CREDENTIALS_DIRECTORY'])/'archive-seed'
            fd = os.open(credential, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                stage = 'authentication'
                with Repository(CACHE, config['root_sha256'], config['metadata_url'], config['targets_url']) as repository:
                    receipt = issue_from_credential(repository, row['target'], snapshot, keyring,
                        job['index'], job['deb'], credential_fd=fd, expected_scope=row['scope'],
                        public_key=bytes.fromhex(config['public_key']),
                        minimum_security_epoch=row['minimum_security_epoch'],
                        maximum_lifetime_seconds=row['maximum_lifetime_seconds'])
            finally:
                os.close(fd)
        stage = 'delivery'
        results.append(sealed(receipt.wire))
        results.append(sealed(receipt.policy_bytes))
        checked, expires = struct.unpack('>QQ', receipt.wire[240:256])
        if (protected(CONFIG, MAX_CONFIG) != config_raw or protected(KEYRING, MAX_KEYRING) != keyring
                or time.monotonic() >= deadline or not checked <= int(time.time()) < expires):
            raise Invalid('observer configuration or time changed before delivery')
        reply = canonical({'schema': 'org.niaos.archive-observer-result/v1', 'request_id': identity,
                           'status': 'authenticated', 'receipt_sha256': sha(receipt.wire),
                           'policy_sha256': sha(receipt.policy_bytes), 'execution_permit': False})
        if connection.sendmsg([reply], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', results))]) != len(reply):
            raise OSError('short observer reply')
    except Exception as exc:
        # No exception text, secret bytes or caller-controlled text in logs.
        # Cache floors may have advanced; rejection does not imply no effects.
        print('archive-observer: '+stage+' rejected ('+type(exc).__name__+')', file=sys.stderr)
        try:
            connection.send(canonical({'schema': 'org.niaos.archive-observer-result/v1',
                'request_id': identity, 'status': 'rejected', 'execution_permit': False}))
        except OSError:
            pass
    finally:
        for fd in descriptors+results:
            os.close(fd)


def provision() -> None:
    raw = protected(CONFIG, MAX_CONFIG)
    config = configuration(raw)
    trusted_root = protected(BOOTSTRAP_ROOT, 512*1024)
    if sha(trusted_root) != config['root_sha256']:
        raise Invalid('observer bootstrap root pin')
    # An interrupted bootstrap is visible and cannot be retried as a new cache.
    write_new(STATE/'bootstrap-intent.json', canonical({'schema': 'org.niaos.archive-observer-bootstrap/v1',
        'configuration_sha256': sha(raw), 'root_sha256': config['root_sha256']}))
    initialize(CACHE, trusted_root, config['root_sha256'], config['metadata_url'], config['targets_url'])
    if protected(CONFIG, MAX_CONFIG) != raw:
        raise Invalid('observer configuration changed during provisioning')
    write_new(STATE/'bootstrap-complete.json', canonical({'schema': 'org.niaos.archive-observer-bootstrap/v1',
        'configuration_sha256': sha(raw), 'root_sha256': config['root_sha256']}))


def main() -> int:
    account = pwd.getpwnam('nia-supply')
    if os.geteuid() == 0 or os.geteuid() != account.pw_uid:
        raise Invalid('dedicated unprivileged observer account required')
    os.umask(0o077)
    if sys.argv[1:] == ['--provision-cache']:
        provision()
        return 0
    if sys.argv[1:]:
        raise Invalid('observer arguments')
    if os.environ.get('LISTEN_PID') != str(os.getpid()) or os.environ.get('LISTEN_FDS') != '1':
        raise Invalid('observer requires exactly one systemd socket')
    with socket.socket(fileno=3) as listener:
        listener.set_inheritable(False)
        if (listener.family != socket.AF_UNIX or listener.type != socket.SOCK_SEQPACKET
                or listener.getsockname() != SOCKET
                or not listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN)):
            raise Invalid('observer activation socket')
        listener.settimeout(5)
        connection, _ = listener.accept()
        with connection:
            handle(connection)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print('archive-observer: startup or provisioning rejected', file=sys.stderr)
        raise SystemExit(1)
