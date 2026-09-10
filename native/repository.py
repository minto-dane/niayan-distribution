# SPDX-License-Identifier: BSD-3-Clause
"""Shared authenticated supply intake using the upstream TUF client.

The cache is trusted supply state, not an installed-package database. Bootstrap
is explicit, from an independently pinned root. Successful target verification
does not authorize installation or attest native effect/configuration closure.
"""
from __future__ import annotations

import base64
import fcntl
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
import uuid
from urllib.parse import urlsplit

import requests
from urllib3.exceptions import HTTPError
from tuf.api import exceptions as tuf_errors
from tuf.api.metadata import Metadata, Root
from tuf.ngclient import Updater, UpdaterConfig
from tuf.ngclient.fetcher import FetcherInterface

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from nia_common import Invalid, canonical, digest, directory_fd, fields, integer, parse_json, read_file, sha, write_new

MAX_METADATA = 5 * 1024 * 1024
MAX_TARGET = 272 * 1024 * 1024
MAX_TRANSFER = 320 * 1024 * 1024
MAX_REQUESTS = 256
MAX_SESSION_SECONDS = 120
MAX_CHECKPOINT = 96 * 1024 * 1024
CONFIG = UpdaterConfig(max_root_rotations=32, max_delegations=32,
                       root_max_length=512 * 1024, timestamp_max_length=16 * 1024,
                       snapshot_max_length=2 * 1024 * 1024,
                       targets_max_length=MAX_METADATA)
TARGET = re.compile(r'[A-Za-z0-9_+.-]+(?:/[A-Za-z0-9_+.-]+)*\Z')


def target_path(value: str) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= 1024 or not TARGET.fullmatch(value)
            or any(p in ('.', '..') for p in value.split('/'))):
        raise Invalid('unsupported repository target path')
    return value


def base_url(value: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        raise Invalid('repository URL size/type')
    parts = urlsplit(value)
    if (parts.scheme != 'https' or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.query or parts.fragment
            or not value.isascii() or any(ord(c) <= 32 or ord(c) == 127 for c in value)
            or '%' in value or '\\' in value):
        raise Invalid('repository requires an explicit HTTPS base without credentials or escapes')
    if parts.path not in ('', '/'):
        target_path(parts.path.strip('/'))
    # Validate the port before a request is made.
    try:
        parts.port
    except ValueError as exc:
        raise Invalid('repository URL port') from exc
    return value.rstrip('/') + '/'


class HTTPSFetcher(FetcherInterface):
    """HTTPS-only, no redirects/proxy environment, bounded requests and bytes."""
    def __init__(self, metadata_url: str, targets_url: str):
        self.bases = (base_url(metadata_url), base_url(targets_url))
        self.session = requests.Session()
        self.session.trust_env = False
        self.started = time.monotonic()
        self.requests = 0
        self.bytes = 0

    def _fetch(self, url):
        try:
            yield from self._stream(url)
        except (requests.RequestException, HTTPError) as exc:
            raise tuf_errors.DownloadError('repository HTTPS transport failed') from exc

    def _stream(self, url):
        if not any(url.startswith(base) and TARGET.fullmatch(url[len(base):]) and
                   all(p not in ('.', '..') for p in url[len(base):].split('/')) for base in self.bases):
            raise tuf_errors.DownloadError('URL outside configured repository')
        self.requests += 1
        if self.requests > MAX_REQUESTS or time.monotonic() - self.started >= MAX_SESSION_SECONDS:
            raise tuf_errors.DownloadError('repository request/time budget')
        with self.session.get(url, stream=True, allow_redirects=False, timeout=(5, 5),
                              headers={'Accept-Encoding': 'identity'}) as response:
            if response.status_code != 200:
                raise tuf_errors.DownloadHTTPError('repository HTTP status', response.status_code)
            if response.headers.get('Content-Encoding', 'identity') != 'identity':
                raise tuf_errors.DownloadError('unexpected HTTP content encoding')
            while True:
                # read1 returns available input rather than accumulating a large
                # chunk indefinitely while a slow peer trickles single bytes.
                chunk = response.raw.read1(64 * 1024, decode_content=False)
                if not chunk:
                    break
                self.bytes += len(chunk)
                if self.bytes > MAX_TRANSFER or time.monotonic() - self.started >= MAX_SESSION_SECONDS:
                    raise tuf_errors.DownloadError('repository transfer/time budget')
                yield chunk

    def close(self):
        self.session.close()


def _private(s, directory=False):
    kind = stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)
    if not kind or s.st_uid != os.geteuid() or s.st_mode & 0o077 or (not directory and s.st_nlink != 1):
        raise Invalid('repository state is not private to its owner')


def _identity(root_sha256, metadata_url, targets_url):
    digest(root_sha256)
    return {'schema': 'org.niaos.repository-cache/v1', 'bootstrap_sha256': root_sha256,
            'metadata_url': base_url(metadata_url), 'targets_url': base_url(targets_url)}


def encode_checkpoint(metadata: dict[str, bytes]) -> bytes:
    if not isinstance(metadata, dict) or not 1 <= len(metadata) <= 128 or 'root.json' not in metadata:
        raise Invalid('checkpoint metadata set')
    total = 0
    for name, raw in metadata.items():
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,170}\.json', name):
            raise Invalid('checkpoint metadata name')
        if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_METADATA:
            raise Invalid('checkpoint metadata size/type')
        total += len(raw)
    if total > 64 * 1024 * 1024:
        raise Invalid('checkpoint total metadata size')
    return canonical({'schema': 'org.niaos.tuf-checkpoint/v1',
                      'metadata': {name: base64.b64encode(raw).decode('ascii') for name, raw in metadata.items()}})


def decode_checkpoint(raw: bytes) -> dict[str, bytes]:
    body = parse_json(raw, limit=MAX_CHECKPOINT)
    fields(body, {'schema', 'metadata'}, 'repository checkpoint')
    if body['schema'] != 'org.niaos.tuf-checkpoint/v1' or not isinstance(body['metadata'], dict) or len(body['metadata']) > 128:
        raise Invalid('checkpoint schema/count')
    result = {}
    try:
        for name, value in body['metadata'].items():
            if not isinstance(value, str) or len(value) > (MAX_METADATA + 2) // 3 * 4:
                raise Invalid('checkpoint encoded metadata size/type')
            result[name] = base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise Invalid('checkpoint encoding') from exc
    encode_checkpoint(result)
    return result


class _RetainedMetadata(FetcherInterface):
    """Serve one exact validated checkpoint to a fresh upstream verifier.

    No network fallback. Delegated roles start outside the temporary cache, so
    their actual use is observable without accessing private Updater attributes.
    """
    def __init__(self, metadata_url, metadata):
        self.files = {}
        self.expiries = {}
        self.used = set()
        self.requests = 0
        for name, raw in metadata.items():
            value = Metadata.from_bytes(raw)
            self.expiries[name] = int(value.signed.expires.timestamp())
            for alias in (name, str(value.signed.version) + '.' + name):
                url = metadata_url + alias
                if url in self.files and self.files[url] != (name, raw):
                    raise Invalid('ambiguous retained metadata name')
                self.files[url] = (name, raw)

    def _fetch(self, url):
        self.requests += 1
        if self.requests > MAX_REQUESTS:
            raise Invalid('retained metadata request budget')
        if url not in self.files:
            raise tuf_errors.DownloadHTTPError('retained metadata absent', 404)
        name, raw = self.files[url]
        self.used.add(name)
        yield raw


def initialize(cache: Path, trusted_root: bytes, expected_root_sha256: str,
               metadata_url: str, targets_url: str):
    """Provision a NEW cache only. Expected digest must come from trusted policy.

    A missing/partially provisioned cache is never silently reset by the client.
    No production key, root metadata or repository URL is supplied by default.
    """
    identity = _identity(expected_root_sha256, metadata_url, targets_url)
    if not isinstance(trusted_root, bytes) or not 1 <= len(trusted_root) <= CONFIG.root_max_length:
        raise Invalid('bootstrap root size/type')
    if sha(trusted_root) != expected_root_sha256:
        raise Invalid('bootstrap root differs from independent pin')
    root = Metadata.from_bytes(trusted_root)
    if not isinstance(root.signed, Root):
        raise Invalid('bootstrap metadata is not a root')
    root.verify_delegate('root', root)
    parent = directory_fd(cache.parent)
    try:
        os.mkdir(cache.name, 0o700, dir_fd=parent)
        os.fsync(parent)
    finally:
        os.close(parent)
    write_new(cache / 'checkpoint.json', encode_checkpoint({'root.json': trusted_root}))
    write_new(cache / 'repository.json', canonical(identity))
    write_new(cache / 'writer.lock', b'')


class Repository:
    """One context owns one cache lock and one fresh TUF update session."""
    def __init__(self, cache: Path, root_sha256: str, metadata_url: str, targets_url: str,
                 *, fetcher: FetcherInterface | None = None):
        self.cache = Path(cache)
        self.identity = _identity(root_sha256, metadata_url, targets_url)
        self.fetcher = fetcher
        self.owned_fetcher = fetcher is None
        self.directory = None
        self.lock = None
        self.updater = None
        self.started = None
        self.failed = False
        self.target_count = 0
        self.target_bytes = 0
        self.stage = None
        self.checkpoint_digest = None

    def _read_cache(self, name, limit):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=self.directory)
        try:
            before = os.fstat(fd)
            _private(before)
            if before.st_size > limit:
                raise Invalid('repository state size')
            chunks, length = [], 0
            while chunk := os.read(fd, min(1024 * 1024, limit + 1 - length)):
                chunks.append(chunk)
                length += len(chunk)
                if length > limit:
                    raise Invalid('repository state grew during read')
            raw = b''.join(chunks)
            after = os.fstat(fd)
            if (len(raw) != before.st_size or
                (before.st_mtime_ns, before.st_ctime_ns, before.st_size) !=
                (after.st_mtime_ns, after.st_ctime_ns, after.st_size)):
                raise Invalid('repository state changed while reading')
            return raw
        finally:
            os.close(fd)

    def _check_cache(self):
        _private(os.fstat(self.directory), True)
        names = os.listdir(self.directory)
        if len(names) > 32:
            raise Invalid('repository metadata file count')
        for name in names:
            temporary = bool(re.fullmatch(r'\.cache-tmp-[a-f0-9]{32}', name))
            if name not in ('writer.lock', 'repository.json', 'checkpoint.json') and not temporary:
                raise Invalid('unsupported metadata cache name')
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                         dir_fd=self.directory)
            try:
                s = os.fstat(fd)
                _private(s)
                if s.st_size > MAX_CHECKPOINT:
                    raise Invalid('repository metadata size budget')
            finally:
                os.close(fd)
            if temporary:
                # Only unreferenced, interrupted checkpoint staging objects;
                # the complete checkpoint itself is never removed or reset.
                os.unlink(name, dir_fd=self.directory)
        # Check the lock name is still the inode we own; do not continue after
        # accidental deletion/replacement of the reservation.
        held, named = os.fstat(self.lock), os.stat('writer.lock', dir_fd=self.directory, follow_symlinks=False)
        if (held.st_dev, held.st_ino) != (named.st_dev, named.st_ino):
            raise Invalid('repository reservation changed')

    def _commit_checkpoint(self):
        self._check_cache()
        stage = Path(self.stage.name)
        names = os.listdir(stage)
        if len(names) > 128:
            raise Invalid('staged metadata count')
        raw = encode_checkpoint({name: read_file(stage / name, MAX_METADATA) for name in names})
        expected = sha(raw)
        if expected == self.checkpoint_digest:
            return
        temporary = '.cache-tmp-' + uuid.uuid4().hex
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                     0o600, dir_fd=self.directory)
        created = True
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, 'checkpoint.json', src_dir_fd=self.directory, dst_dir_fd=self.directory)
            created = False
            os.fsync(self.directory)
            self.checkpoint_digest = expected
        finally:
            if created:
                os.unlink(temporary, dir_fd=self.directory)

    def __enter__(self):
        if self.directory is not None or self.failed:
            raise Invalid('repository context cannot be reused')
        try:
            self.directory = directory_fd(self.cache)
            _private(os.fstat(self.directory), True)
            self.lock = os.open('writer.lock', os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                                dir_fd=self.directory)
            _private(os.fstat(self.lock))
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._check_cache()
            if parse_json(self._read_cache('repository.json', 8192)) != self.identity:
                raise Invalid('repository cache identity differs from trusted policy')
            checkpoint = self._read_cache('checkpoint.json', MAX_CHECKPOINT)
            metadata = decode_checkpoint(checkpoint)
            self.checkpoint_digest = sha(checkpoint)
            # Upstream may replace or discard several role files during key
            # rotation. Work privately and publish all version floors together,
            # so interruption cannot leave a partially updated trust cache.
            self.stage = tempfile.TemporaryDirectory(prefix='nia-metadata-')
            for name, raw in metadata.items():
                write_new(Path(self.stage.name) / name, raw)
            if self.fetcher is None:
                self.fetcher = HTTPSFetcher(self.identity['metadata_url'], self.identity['targets_url'])
            self.started = time.monotonic()
            self.updater = Updater(self.stage.name, self.identity['metadata_url'],
                                   target_base_url=self.identity['targets_url'],
                                   fetcher=self.fetcher, config=CONFIG)
            self.updater.refresh()
            self._commit_checkpoint()
            return self
        except BaseException:
            self.failed = True
            self.close()
            raise

    def target(self, path: str, limit=MAX_TARGET) -> bytes:
        if self.updater is None or self.failed:
            raise Invalid('repository session is not usable')
        try:
            target_path(path)
            integer(limit, 1, MAX_TARGET, 'target byte limit')
            if time.monotonic() - self.started >= MAX_SESSION_SECONDS:
                raise Invalid('repository session expired; reopen and revalidate')
            self._check_cache()
            info = self.updater.get_targetinfo(path)
            if info is None:
                raise Invalid('target is absent from authenticated repository')
            if type(info.length) is not int or not 1 <= info.length <= limit:
                raise Invalid('target length outside native intake budget')
            digest(info.hashes.get('sha256'))
            self.target_count += 1
            self.target_bytes += info.length
            if self.target_count > MAX_REQUESTS or self.target_bytes > MAX_TRANSFER:
                raise Invalid('aggregate target budget')
            with tempfile.TemporaryDirectory(prefix='nia-target-') as temporary:
                output = Path(temporary) / 'artifact'
                self.updater.download_target(info, str(output))
                raw = read_file(output, limit)
                info.verify_length_and_hashes(raw)
            self._commit_checkpoint()
            if time.monotonic() - self.started >= MAX_SESSION_SECONDS:
                raise Invalid('repository session expired during download')
            return raw
        except BaseException:
            self.failed = True
            raise

    def revalidate_target(self, path: str, raw: bytes) -> int:
        """Revalidate retained target metadata now, returning its expiry bound.

        A fresh upstream verifier uses an ephemeral copy of our locked, current
        checkpoint. This is not a remote refresh, a new persistent trust cache,
        an initial-root reset, or permission to execute the authenticated bytes.
        """
        if self.updater is None or self.failed:
            raise Invalid('repository session is not usable')
        try:
            target_path(path)
            if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_TARGET:
                raise Invalid('retained target byte limit')
            if time.monotonic() - self.started >= MAX_SESSION_SECONDS:
                raise Invalid('repository session expired before revalidation')
            self.target_count += 1
            if self.target_count > MAX_REQUESTS:
                raise Invalid('aggregate target budget')
            before = int(time.time())
            self._check_cache()
            checkpoint = self._read_cache('checkpoint.json', MAX_CHECKPOINT)
            if sha(checkpoint) != self.checkpoint_digest:
                raise Invalid('retained checkpoint changed during session')
            if parse_json(self._read_cache('repository.json', 8192)) != self.identity:
                raise Invalid('repository cache identity changed during session')
            metadata = decode_checkpoint(checkpoint)
            fetcher = _RetainedMetadata(self.identity['metadata_url'], metadata)
            top = {'root.json', 'timestamp.json', 'snapshot.json', 'targets.json'}
            if not top <= set(metadata):
                raise Invalid('retained top-level metadata missing')
            with tempfile.TemporaryDirectory(prefix='nia-revalidation-') as temporary:
                for name in top:
                    write_new(Path(temporary) / name, metadata[name])
                fresh = Updater(temporary, self.identity['metadata_url'],
                                target_base_url=self.identity['targets_url'], fetcher=fetcher, config=CONFIG)
                fresh.refresh()
                info = fresh.get_targetinfo(path)
                if info is None:
                    raise Invalid('target absent from retained verified metadata')
                digest(info.hashes.get('sha256'))
                info.verify_length_and_hashes(raw)
            expires = min(fetcher.expiries[name] for name in top | fetcher.used)
            self._check_cache()
            if sha(self._read_cache('checkpoint.json', MAX_CHECKPOINT)) != self.checkpoint_digest:
                raise Invalid('retained checkpoint changed during revalidation')
            if parse_json(self._read_cache('repository.json', 8192)) != self.identity:
                raise Invalid('repository cache identity changed during revalidation')
            after = int(time.time())
            if after < before or after >= expires or time.monotonic() - self.started >= MAX_SESSION_SECONDS:
                raise Invalid('retained metadata expired during revalidation or clock moved backward')
            return expires
        except BaseException:
            self.failed = True
            raise

    def close(self):
        self.updater = None
        try:
            if self.stage is not None:
                self.stage.cleanup()
        finally:
            self.stage = None
            if self.lock is not None:
                os.close(self.lock)
                self.lock = None
            if self.directory is not None:
                os.close(self.directory)
                self.directory = None
            if self.owned_fetcher and self.fetcher is not None:
                self.fetcher.close()
            self.failed = True

    def __exit__(self, *_):
        self.close()
