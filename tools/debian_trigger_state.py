# SPDX-License-Identifier: MIT
"""Bounded reference state for deferred DEB triggers, without handler execution.

State bytes may be bound into a transaction's existing CAS/WAL. This module has
no filesystem, executor, installed database or authority. Success transitions
model an external observation; the native adapter must independently verify it.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import deque

from debian_triggers import Delivery, MAX_EVENTS, MAX_ROUTES, pending as batch_view, trigger_name
from nia_common import Invalid, canonical, digest, fields, integer, parse_json, sha

MAX_STATE_BYTES = 16 * 1024 * 1024
SCHEMA = 'org.niaos.trigger-state-reference/v1'


def _pairs(rows, limit, names=False):
    if type(rows) is not tuple or len(rows) > limit:
        raise Invalid('trigger state table bound')
    for pair in rows:
        if type(pair) is not tuple or len(pair) != 2:
            raise Invalid('trigger state pair shape')
        digest(pair[0])
        (trigger_name if names else digest)(pair[1])
        if not names and pair[0] == pair[1]:
            raise Invalid('self-awaiting trigger')
    if rows != tuple(sorted(set(rows))):
        raise Invalid('trigger state table is not canonical')


@dataclass(frozen=True)
class Running:
    receiver: str
    names: tuple[str, ...]
    started_revision: int

    def __post_init__(self):
        digest(self.receiver)
        integer(self.started_revision, 1)
        if type(self.names) is not tuple or not 1 <= len(self.names) <= MAX_EVENTS:
            raise Invalid('active trigger name bound')
        for name in self.names:
            trigger_name(name)
        if self.names != tuple(sorted(set(self.names))):
            raise Invalid('active trigger names are not canonical')


@dataclass(frozen=True)
class State:
    binding: str
    revision: int = 0
    pending: tuple[tuple[str, str], ...] = ()
    awaited: tuple[tuple[str, str], ...] = ()
    running: Running | None = None

    def __post_init__(self):
        digest(self.binding)
        integer(self.revision)
        _pairs(self.pending, MAX_EVENTS, names=True)
        _pairs(self.awaited, MAX_ROUTES)
        receivers = {receiver for receiver, _ in self.pending}
        receivers.update(origin for origin, _ in self.awaited)
        if self.running is not None:
            if type(self.running) is not Running:
                raise Invalid('typed active trigger batch required')
            self.running.__post_init__()
            if self.running.started_revision > self.revision:
                raise Invalid('active trigger revision is in the future')
            receivers.add(self.running.receiver)
        if any(receiver not in receivers for _, receiver in self.awaited):
            raise Invalid('awaited receiver has no outstanding trigger work')
        if self.revision == 0 and (self.pending or self.awaited or self.running):
            raise Invalid('initial trigger state is not empty')


def _next(state):
    if type(state) is not State:
        raise Invalid('typed trigger state required')
    state.__post_init__()
    if state.revision == 2**63 - 1:
        raise Invalid('trigger state revision exhausted')
    return state.revision + 1


def activate(state: State, deliveries: tuple[Delivery, ...]) -> State:
    revision = _next(state)
    view = batch_view(deliveries)
    pending = set(state.pending)
    awaited = set(state.awaited)
    pending.update((receiver, name) for receiver, names in view['pending'].items() for name in names)
    awaited.update((origin, receiver) for origin, receivers in view['awaited'].items() for receiver in receivers)
    # Active names remain frozen. A repeated activation during a handler creates
    # NEW pending work, even when its name is also in the current handler's batch.
    result = State(state.binding, revision, tuple(sorted(pending)), tuple(sorted(awaited)), state.running)
    encode(result)  # Bound the actual checkpoint encoding before returning it.
    if result.pending == state.pending and result.awaited == state.awaited:
        return state
    return result


def start(state: State, receiver: str) -> State:
    revision = _next(state)
    digest(receiver)
    if state.running is not None:
        raise Invalid('active trigger handler requires reconciliation')
    names = tuple(name for target, name in state.pending if target == receiver)
    if not names:
        raise Invalid('receiver has no pending triggers')
    result = State(state.binding, revision,
                   tuple(pair for pair in state.pending if pair[0] != receiver), state.awaited,
                   Running(receiver, names, revision))
    encode(result)
    return result


def attempt(state: State) -> str:
    state.__post_init__()
    if state.running is None:
        raise Invalid('no active trigger handler')
    active = state.running
    return sha(canonical(dict(domain='org.niaos.trigger-attempt/v1', binding=state.binding,
                              revision=active.started_revision, receiver=active.receiver,
                              names=list(active.names))))


def observe_success(state: State, expected_attempt: str) -> State:
    """Model a separately verified completion, NOT permission or verification.

    A missing reply or failed handler must retain the original state. Restarting
    a stored running batch is never an implicit result of decoding/recovery.
    """
    revision = _next(state)
    digest(expected_attempt)
    if expected_attempt != attempt(state):
        raise Invalid('completion is for a different trigger attempt')
    receiver = state.running.receiver
    # Waiters wait for the PACKAGE, not just the particular names in this batch.
    # A new noawait activation cannot release old awaiters while work remains.
    busy = {target for target, _ in state.pending}
    incoming, outgoing = {}, {}
    awaited = set(state.awaited)
    for origin, target in awaited:
        incoming.setdefault(target, set()).add(origin)
        outgoing[origin] = outgoing.get(origin, 0) + 1
    ready = deque([receiver] if receiver not in busy and not outgoing.get(receiver) else [])
    # Becoming free of awaited work can release another package's waiters.
    # Traverse each edge once; cycles with outstanding waits are not cleared.
    while ready:
        target = ready.popleft()
        for origin in incoming.get(target, ()):
            awaited.remove((origin, target))
            outgoing[origin] -= 1
            if not outgoing[origin] and origin not in busy:
                ready.append(origin)
    return State(state.binding, revision, state.pending, tuple(sorted(awaited)))


def encode(state: State) -> bytes:
    state.__post_init__()
    active = state.running
    size = 512  # Conservative framing allowance; bound before a large encoding.
    for rows in (state.pending, state.awaited, () if active is None else active.names):
        for row in rows:
            size += len(canonical(row)) + 1
            if size > MAX_STATE_BYTES:
                raise Invalid('trigger state byte limit')
    raw = canonical(dict(schema=SCHEMA, binding=state.binding, revision=state.revision,
        pending=[list(pair) for pair in state.pending], awaited=[list(pair) for pair in state.awaited],
        running=None if active is None else dict(receiver=active.receiver, names=list(active.names),
                                                started_revision=active.started_revision),
        execution_permit=False))
    if len(raw) > MAX_STATE_BYTES:
        raise Invalid('trigger state byte limit')
    return raw


def decode(raw: bytes, expected_binding: str, expected_digest: str) -> State:
    digest(expected_binding)
    digest(expected_digest)
    if type(raw) is not bytes or len(raw) > MAX_STATE_BYTES or sha(raw) != expected_digest:
        raise Invalid('trigger checkpoint content mismatch')
    value = parse_json(raw, limit=MAX_STATE_BYTES)
    fields(value, 'schema binding revision pending awaited running execution_permit')
    if (value['schema'] != SCHEMA or value['binding'] != expected_binding
            or value['execution_permit'] is not False):
        raise Invalid('trigger checkpoint binding or schema mismatch')
    for key, limit in (('pending', MAX_EVENTS), ('awaited', MAX_ROUTES)):
        rows = value[key]
        if type(rows) is not list or len(rows) > limit or any(type(row) is not list for row in rows):
            raise Invalid('trigger checkpoint table shape')
    active = value['running']
    if active is not None:
        fields(active, 'receiver names started_revision')
        if type(active['names']) is not list:
            raise Invalid('trigger checkpoint name list shape')
        active = Running(active['receiver'], tuple(active['names']), active['started_revision'])
    result = State(value['binding'], value['revision'], tuple(map(tuple, value['pending'])),
                   tuple(map(tuple, value['awaited'])), active)
    if encode(result) != raw:
        raise Invalid('trigger checkpoint is not canonical')
    return result
