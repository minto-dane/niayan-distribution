# SPDX-License-Identifier: MIT
"""Native DEB trigger declarations and activation routing, without execution.

The caller supplies independently authenticated package identities and the
interests effective at EACH lifecycle boundary. Routing is not handler execution,
phase admission, filesystem monitoring, a grant, or a second installed database.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

from nia_common import Invalid, digest, relative

MAX_BYTES = 1024 * 1024
MAX_DIRECTIVES = 4096
MAX_EVENTS = 65536
MAX_ROUTES = 262144
DIRECTIVES = {
    'interest': ('interest', True), 'interest-await': ('interest', True),
    'interest-noawait': ('interest', False), 'activate': ('activate', True),
    'activate-await': ('activate', True), 'activate-noawait': ('activate', False),
}
STATE_OPERATIONS = frozenset(('unpack', 'configure', 'remove', 'purge', 'deconfigure', 'disappear'))
NO_ACTIVATION_OPERATIONS = frozenset(('process-triggers', 'finish-awaited'))


def trigger_name(name: str) -> str:
    if not isinstance(name, str) or not 1 <= len(name) <= 4096:
        raise Invalid('trigger name size')
    if name.startswith('/'):
        if name != '/':
            relative(name[1:])
        if any(c.isspace() for c in name) or '#' in name:
            raise Invalid('unsupported whitespace or comment delimiter in file trigger')
    elif not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9+_.-]*', name):
        raise Invalid('unsupported explicit trigger name')
    return name


@dataclass(frozen=True, order=True)
class Directive:
    kind: str
    name: str
    await_completion: bool

    def __post_init__(self):
        if self.kind not in ('interest', 'activate') or type(self.await_completion) is not bool:
            raise Invalid('invalid trigger directive')
        trigger_name(self.name)


def parse(raw: bytes) -> tuple[Directive, ...]:
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise Invalid('trigger declaration size')
    try:
        text = raw.decode('utf-8')
    except UnicodeError as exc:
        raise Invalid('trigger declaration encoding') from exc
    if any(ord(c) < 32 and c not in '\t\n\r' or ord(c) == 127 for c in text):
        raise Invalid('control character in trigger declarations')
    rows = {}
    lines = 0
    for line in text.split('\n'):
        if len(line) > 8192:
            raise Invalid('trigger declaration line size')
        line = line.split('#', 1)[0].strip(' \t\r')
        if not line:
            continue
        words = line.split()
        if len(words) != 2 or words[0] not in DIRECTIVES:
            raise Invalid('unknown or malformed trigger directive')
        kind, await_completion = DIRECTIVES[words[0]]
        entry = Directive(kind, words[1], await_completion)
        key = (kind, entry.name)
        if key in rows and rows[key] != entry:
            raise Invalid('conflicting duplicate trigger directive')
        rows[key] = entry
        lines += 1
        if lines > MAX_DIRECTIVES:
            raise Invalid('trigger declaration count')
    return tuple(sorted(rows.values()))


def describe(raw: bytes) -> list[dict]:
    return [dict(kind=d.kind, name=d.name, await_completion=d.await_completion) for d in parse(raw)]


@dataclass(frozen=True, order=True)
class Activation:
    name: str
    origin: str
    await_completion: bool

    def __post_init__(self):
        trigger_name(self.name)
        digest(self.origin)
        if type(self.await_completion) is not bool:
            raise Invalid('invalid trigger activation awaiting mode')


def _declarations(items):
    if not isinstance(items, tuple) or len(items) > MAX_DIRECTIVES or any(type(d) is not Directive for d in items):
        raise Invalid('bounded parsed trigger declarations required')
    # Check aliases/modes even when callers construct the values themselves.
    seen = {}
    for d in items:
        d.__post_init__()
        key = (d.kind, d.name)
        if key in seen and seen[key] != d:
            raise Invalid('conflicting duplicate trigger directive')
        seen[key] = d


def state_activations(origin: str, operation: str, before: tuple[Directive, ...],
                      after: tuple[Directive, ...] = ()) -> tuple[Activation, ...]:
    digest(origin)
    _declarations(before)
    _declarations(after)
    if operation not in STATE_OPERATIONS | NO_ACTIVATION_OPERATIONS:
        raise Invalid('unknown trigger lifecycle operation')
    if after and operation != 'unpack':
        raise Invalid('new trigger declarations only apply to unpack')
    if operation in NO_ACTIVATION_OPERATIONS:
        return ()
    declarations = before + after if operation == 'unpack' else before
    # Unpack activates declarations from BOTH the old and new versions.
    # Multiple activations coalesce; a noawait request never clears an await.
    names = {}
    for d in declarations:
        if d.kind == 'activate':
            names[d.name] = names.get(d.name, False) or d.await_completion
    return tuple(Activation(n, origin, mode) for n, mode in sorted(names.items()))


def _interests(packages: dict[str, tuple[Directive, ...]]):
    if type(packages) is not dict or len(packages) > 4096:
        raise Invalid('trigger interest package count')
    total = 0
    for package, declarations in sorted(packages.items()):
        digest(package)
        _declarations(declarations)
        for d in declarations:
            total += 1
            if total > MAX_EVENTS:
                raise Invalid('total trigger declaration limit')
            if d.kind == 'interest':
                yield package, d


def file_activations(origin: str, changed_paths: tuple[str, ...],
                     packages: dict[str, tuple[Directive, ...]]) -> tuple[Activation, ...]:
    digest(origin)
    if not isinstance(changed_paths, tuple) or len(changed_paths) > MAX_EVENTS:
        raise Invalid('bounded file-change batch required')
    interests = {d.name for _, d in _interests(packages) if d.name.startswith('/')}
    matches = set()
    path_bytes = 0
    for name in changed_paths:
        # Paths are archive-relative. No host symlink resolution or path aliases.
        relative(name)
        if '/' in interests:
            matches.add('/')
        parts = name.split('/')
        path_bytes += len(name.encode('utf-8'))
        if len(parts) > 64 or path_bytes > 16 * 1024 * 1024:
            raise Invalid('file trigger batch path budget')
        for count in range(1, len(parts) + 1):
            prefix = '/' + '/'.join(parts[:count])
            if prefix in interests:
                matches.add(prefix)
    # File activations occur before the corresponding native file operation.
    # The interest's noawait mode will suppress waiting during routing.
    return tuple(Activation(name, origin, True) for name in sorted(matches))


@dataclass(frozen=True, order=True)
class Delivery:
    receiver: str
    name: str
    origin: str
    await_completion: bool


def route(activations: tuple[Activation, ...],
          packages: dict[str, tuple[Directive, ...]]) -> tuple[Delivery, ...]:
    if not isinstance(activations, tuple) or len(activations) > MAX_EVENTS:
        raise Invalid('bounded trigger activations required')
    interests = {}
    for package, d in _interests(packages):
        interests.setdefault(d.name, {})[package] = d.await_completion
    result = {}
    for a in activations:
        if type(a) is not Activation:
            raise Invalid('typed trigger activation required')
        a.__post_init__()
        for receiver, interested_await in interests.get(a.name, {}).items():
            key = (receiver, a.name, a.origin)
            # A package cannot await itself. It may still receive its own trigger.
            waiting = a.await_completion and interested_await and receiver != a.origin
            waiting = waiting or result.get(key, False)
            result[key] = waiting
            if len(result) > MAX_ROUTES:
                raise Invalid('trigger delivery limit')
    return tuple(Delivery(*key, mode) for key, mode in sorted(result.items()))


def pending(deliveries: tuple[Delivery, ...]) -> dict:
    """Coalesce one observed batch for a future native WAL; writes no database.

    Existing pending/awaited state, handler completion and nested activations
    belong to the native lifecycle transaction. This view cannot clear them.
    """
    if not isinstance(deliveries, tuple) or len(deliveries) > MAX_ROUTES:
        raise Invalid('bounded trigger deliveries required')
    receivers, awaited = {}, {}
    for d in deliveries:
        if type(d) is not Delivery or type(d.await_completion) is not bool:
            raise Invalid('typed trigger delivery required')
        digest(d.receiver)
        digest(d.origin)
        trigger_name(d.name)
        if d.await_completion and d.origin == d.receiver:
            raise Invalid('self-awaiting trigger')
        receivers.setdefault(d.receiver, set()).add(d.name)
        if d.await_completion:
            awaited.setdefault(d.origin, set()).add(d.receiver)
    return dict(pending={k: sorted(v) for k, v in sorted(receivers.items())},
                awaited={k: sorted(v) for k, v in sorted(awaited.items())},
                handlers_executed=False, execution_permit=False)
