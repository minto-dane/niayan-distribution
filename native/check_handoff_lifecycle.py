# SPDX-License-Identifier: BSD-3-Clause
"""Exhaustive finite control check of the runtime transition function.

No I/O, memory safety, interpreter or authority proof is claimed. Ghost history
is independent of the implementation phase and is never reset by failure/close.
There is no search-depth cutoff: all reachable finite configurations are visited.
"""
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
import json

from root_handoff import Event, Phase, Rejected, transition


@dataclass(frozen=True)
class History:
    phase: Phase = Phase.STARTING
    requests: int = 0
    accepts: int = 0
    completions: int = 0
    acknowledgments: int = 0
    sealed: bool = False


def check(step: Callable[[Phase, Event], Phase] = transition) -> dict[str, int]:
    if not __debug__:
        raise RuntimeError('assertions must be enabled for exhaustive checking')
    initial = History()
    pending = deque([initial])
    reached = {initial}
    accepted = rejected = 0
    while pending:
        before = pending.popleft()
        for event in Event:
            try:
                phase = step(before.phase, event)
            except Rejected:
                rejected += 1
                continue
            accepted += 1
            assert isinstance(phase, Phase)
            assert not before.sealed or event in (Event.CLOSE, Event.FAIL), 'terminal state reopened'
            after = History(phase,
                before.requests + int(event is Event.RECEIVE),
                before.accepts + int(event is Event.ACCEPT),
                before.completions + int(event is Event.COMPLETE),
                before.acknowledgments + int(event is Event.ACK),
                before.sealed or event in (Event.FAIL, Event.CLOSE))
            assert 0 <= after.acknowledgments <= after.completions <= after.accepts <= after.requests <= 1, 'history order or replay'
            assert phase is not Phase.COMPLETE or after.acknowledgments == 1, 'success without acknowledgment'
            assert event is not Event.CLOSE or phase is Phase.CLOSED, 'close not terminal'
            if after not in reached:
                reached.add(after)
                pending.append(after)
    assert {node.phase for node in reached} == set(Phase), 'unreachable phase/vacuous check'
    assert any(node.acknowledgments == 1 for node in reached), 'success path unreachable'
    return dict(configurations=len(reached), accepted_edges=accepted, rejected_edges=rejected)


if __name__ == '__main__':
    report: dict[str, str | bool | int] = {
        'result': 'pass', 'scope': 'finite channel control and ghost history only',
        'complete_runtime_proof': False,
    }
    report.update(check())
    print(json.dumps(report, indent=2))
