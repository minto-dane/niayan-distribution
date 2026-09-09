# SPDX-License-Identifier: MIT
"""Bounded offline build-tool primitives. Not part of the privileged SPARK core."""
from __future__ import annotations
import hashlib, json, os, stat, uuid
from pathlib import Path

class Invalid(ValueError):
    """Malformed, unsupported, stale, or unauthenticated input; no permission implied."""

MAX_JSON = 8 * 1024 * 1024

def fields(obj, keys, where='object'):
    expected=set(keys.split()) if isinstance(keys,str) else set(keys)
    if type(obj) is not dict or set(obj) != expected:
        raise Invalid(where+': unknown or missing fields')

def integer(value, low=0, high=2**63-1, where='integer'):
    if type(value) is not int or not low <= value <= high:
        raise Invalid(where+': out-of-range/noncanonical integer')
    return value

def digest(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value) or value == '0'*64:
        raise Invalid('noncanonical or absent SHA-256')
    return value

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('ascii')

def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise Invalid('duplicate JSON field')
        result[key] = value
    return result

def _number(_):
    raise Invalid('floating point and nonfinite values are not supported')

def parse_json(raw: bytes, *, limit=MAX_JSON):
    if len(raw) > limit:
        raise Invalid('JSON byte limit')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                          parse_float=_number, parse_constant=_number)
    except Invalid:
        raise
    except (ValueError, RecursionError) as exc:
        # The interpreter's bounded integer conversion raises ValueError,
        # rather than JSONDecodeError, for an oversized numeric token.
        raise Invalid('invalid JSON') from exc

def relative(text: str) -> str:
    if not isinstance(text, str) or not 1 <= len(text) <= 4096 or text.startswith('/') or '\\' in text:
        raise Invalid('invalid relative path')
    try: text.encode('utf-8',errors='strict')
    except UnicodeError as exc: raise Invalid('non-Unicode path') from exc
    if any(c < ' ' or ord(c) == 127 for c in text) or any(p in ('', '.', '..') for p in text.split('/')):
        raise Invalid('noncanonical relative path')
    return text

def directory_fd(path: Path | str) -> int:
    """Walk all parents without following links, including a caller's root path."""
    raw = os.path.abspath(os.fspath(path))
    parts = Path(raw).parts[1:]
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in parts:
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd); fd = new
        return fd
    except BaseException:
        os.close(fd); raise

def read_at(root: Path | str, name: str, limit=MAX_JSON, *, owner: int | None = None) -> bytes:
    parts = relative(name).split('/')
    parent = directory_fd(root)
    try:
        for part in parts[:-1]:
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            os.close(parent); parent = new
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
                raise Invalid('input is not a bounded regular file')
            if owner is not None and (before.st_uid != owner or before.st_mode & 0o022 or before.st_nlink != 1):
                raise Invalid('input is not protected policy owned by the expected authority')
            chunks=[]; count=0
            while True:
                chunk = os.read(fd, min(1024*1024, limit+1-count))
                if not chunk: break
                count += len(chunk)
                if count > limit: raise Invalid('input size limit')
                chunks.append(chunk)
            after = os.fstat(fd)
            def token(s): return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid)
            if token(before) != token(after) or count != before.st_size:
                raise Invalid('input changed while reading')
            return b''.join(chunks)
        finally:
            os.close(fd)
    finally:
        os.close(parent)

def read_file(path: Path | str, limit=MAX_JSON, *, owner: int | None = None) -> bytes:
    p=Path(path)
    return read_at(p.parent,p.name,limit,owner=owner)

def write_new(path: Path | str, data: bytes) -> None:
    """Publish only to an absent name; never replace a user's file or a symlink."""
    p=Path(path); relative(p.name)
    directory=directory_fd(p.parent)
    temporary='.nia-new-'+uuid.uuid4().hex
    fd=None; created=False
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_CLOEXEC|os.O_NOFOLLOW,0o600,dir_fd=directory)
        created=True
        view=memoryview(data)
        while view:
            n=os.write(fd,view)
            if n<=0: raise OSError('short write')
            view=view[n:]
        os.fsync(fd);os.close(fd);fd=None
        os.link(temporary,p.name,src_dir_fd=directory,dst_dir_fd=directory,follow_symlinks=False)
        os.fsync(directory)
    finally:
        if fd is not None: os.close(fd)
        if created:
            os.unlink(temporary,dir_fd=directory)
            os.fsync(directory)
        os.close(directory)

def hash_file_at(root:Path|str,path:str,limit=8*1024**3)->tuple[str,int]:
    """Streaming counterpart of read_at for large source objects; no extraction."""
    parts=relative(path).split('/');parent=directory_fd(root)
    try:
        for part in parts[:-1]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC|os.O_NOFOLLOW,dir_fd=parent)
            os.close(parent);parent=child
        fd=os.open(parts[-1],os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size>limit:raise Invalid('source blob not bounded regular file')
            h=hashlib.sha256();total=0
            while chunk:=os.read(fd,1024*1024):
                total+=len(chunk)
                if total>limit:raise Invalid('source blob grows beyond limit')
                h.update(chunk)
            after=os.fstat(fd)
            token=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_gid,s.st_mode)
            if total!=before.st_size or token(before)!=token(after):raise Invalid('source blob changed during hashing')
            return h.hexdigest(),total
        finally:os.close(fd)
    finally:os.close(parent)
