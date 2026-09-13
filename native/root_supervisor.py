# SPDX-License-Identifier: BSD-3-Clause
"""Integrate private handoffs, current authorization and a held root controller.

No listener or public launch path. A trusted launcher must supply the native
admission provider and independently selected scope. That provider must check
current supply, generation reservation and exact-plan consent, without blocking
or converting polkit's observation into any of those permissions.
"""
from __future__ import annotations

import os
import select
from typing import Protocol

from operator_guard import OperatorGuard, Phase as OperatorPhase
from plan_consent import PlanConsent
from root_handoff import Channel, Phase as ChannelPhase, ReinspectionScope, Rejected, Scope, now_ms
from root_session_client import Phase as SessionPhase, RootIdentity, RootSession


class Admission(Protocol):
    """Mandatory current native evidence check; raise on absence or uncertainty.

    Implementations must retain their real native reservations throughout this
    supervisor's lifetime and provide a bounded, nonblocking check. There is no
    default implementation. A successful mock is not production admission.
    """
    def check(self, scope: Scope, plan: bytes, request: bytes, boundary: str) -> None: ...


class Supervisor:
    """Own the supplied session/operator/channels; borrow native admission.

    One original deadline, no automatic retry or regenerated request. Callers
    use a with block and retain the nonroot child and native admission until
    after exit. Closing disconnects the controller before reaping the operator;
    remote worker cancellation/sealing remain the controller's responsibility.
    """
    def __init__(self, session: RootSession, operator: OperatorGuard, admission: Admission,
                 *, consent: PlanConsent) -> None:
        self.owner = os.getpid()
        self.session, self.operator, self.admission = session, operator, admission
        self.consent = consent
        self.channels: list[Channel] = []
        self.closed = False
        self.observation = 0
        self.observed_at = 0
        self.next_check = now_ms()
        if (os.getuid() or os.geteuid() or session.phase is not SessionPhase.NEW
                or operator.phase is not OperatorPhase.NEW
                or session.scope.deadline != operator.original_deadline):
            raise Rejected('supervisor-context')
        consent.check(operator.plan, session.scope.generation, operator.request, session.scope.deadline)
        if consent.peer is None or operator.peer is None:
            raise Rejected('supervisor-confirmed-peer-required')
        confirmed, authenticated = os.fstat(consent.peer.fileno()), os.fstat(operator.peer.fileno())
        if (confirmed.st_dev, confirmed.st_ino) != (authenticated.st_dev, authenticated.st_ino):
            raise Rejected('supervisor-consent-and-operator-peer-differ')

    def _current(self) -> None:
        if self.closed or self.owner != os.getpid() or os.getuid() or os.geteuid():
            raise Rejected('supervisor-owner-or-ended')
        self.session.current()
        self.consent.check(self.operator.plan, self.session.scope.generation,
                           self.operator.request, self.session.scope.deadline)
        self.operator.descriptors()
        for channel in self.channels:
            channel._alive()
            if channel.phase in (ChannelPhase.RECEIVED, ChannelPhase.COMPLETE):
                channel._current()
            elif channel.phase is not ChannelPhase.READY:
                raise Rejected('supervisor-channel-state')
        self.admission.check(self.session.scope, self.operator.plan, self.operator.request, 'hold')

    def _operator(self) -> None:
        if self.operator.phase is OperatorPhase.PENDING:
            observed = self.operator.receive()
            if observed is not None:
                self.observation = observed.sequence
                self.observed_at = observed.finished
                self.next_check = min(self.operator.original_deadline, observed.finished + 250)
        elif now_ms() >= self.next_check:
            self.operator.request_check()

    def _wait(self, target: int | None = None, *, sequence: int | None = None) -> None:
        for _ in range(16_384):
            self._current()
            self._operator()
            self._current()
            if sequence is not None and self.observation > sequence:
                return
            poll = select.poll()
            descriptors = self.operator.descriptors()
            # An idle stdout is deliberately excluded after consuming a reply;
            # unsolicited helper data then cannot drive an unbounded busy loop.
            for fd in (descriptors[1], descriptors[2], descriptors[3]):
                poll.register(fd, select.POLLIN)
            if self.operator.phase is OperatorPhase.PENDING:
                poll.register(descriptors[0], select.POLLIN)
            controller = self.session.descriptor()
            if controller is not None:
                poll.register(controller, select.POLLIN)
            for channel in self.channels:
                poll.register(channel.pidfd, select.POLLIN)
                assert channel.peer is not None
                if channel.phase is not ChannelPhase.READY or channel.peer.fileno() == target:
                    poll.register(channel.peer, select.POLLIN)
            if target is not None:
                poll.register(target, select.POLLIN)
            until = self.operator.next_deadline if self.operator.phase is OperatorPhase.PENDING else self.next_check
            events = poll.poll(max(1, min(250, until - now_ms())))
            self._current()
            for fd, flags in events:
                if flags & select.POLLNVAL:
                    raise Rejected('supervisor-invalid-descriptor')
                # Let the exact receiver classify response/EOF; cleanup EOF is
                # the only controller disconnect that can complete normally.
                if fd == target:
                    return
                if fd == controller:
                    raise Rejected('supervisor-unsolicited-controller-or-disconnect')
        raise Rejected('supervisor-event-budget')

    def _checkpoint(self, boundary: str) -> None:
        self._current()
        previous = self.operator.sequence
        # A check already pending before this boundary is not its fresh check.
        if self.operator.phase is OperatorPhase.PENDING:
            self._wait(sequence=previous - 1)
        previous = self.operator.sequence
        self.operator.request_check()
        self._wait(sequence=previous)
        self.admission.check(self.session.scope, self.operator.plan, self.operator.request, boundary)
        self._effect_current()

    def _effect_current(self) -> None:
        self._current()
        if (self.operator.phase is not OperatorPhase.OBSERVED or not self.observation
                or not 0 <= now_ms() - self.observed_at <= 1000):
            raise Rejected('supervisor-stale-effect-authorization')

    def _accept(self, channel: Channel) -> tuple[int, int]:
        if channel in self.channels or len(self.channels) >= 2:
            raise Rejected('supervisor-handoff-count')
        self.channels.append(channel)
        assert channel.peer is not None
        self._wait(channel.peer.fileno())
        return channel.receive(wait=False)

    def _reply(self, channel: Channel, boundary: str) -> RootIdentity:
        for _ in range(1200):
            self._wait(self.session.descriptor())
            if self.session.receive():
                break
        else:
            raise Rejected('supervisor-response-budget')
        self._checkpoint(boundary)
        observed = self.session.physical()
        self._effect_current()
        channel.complete(wait=False)
        return observed

    def prepare(self, channel: Channel) -> RootIdentity:
        try:
            if type(channel.scope) is not Scope or channel.scope != self.session.scope:
                raise Rejected('supervisor-prepare-scope')
            archive, lease = self._accept(channel)
            self._checkpoint('prepare-root')
            self.session.prepare(archive, lease)
            return self._reply(channel, 'root-prepared')
        except BaseException:
            self.close()
            raise

    def reinspect(self, channel: Channel) -> RootIdentity:
        try:
            scope, initial = channel.scope, self.session.scope
            if not isinstance(scope, ReinspectionScope) or self.session.phase is not SessionPhase.HELD:
                raise Rejected('supervisor-reinspection-state')
            expected = ReinspectionScope(initial.generation, initial.root_manifest, initial.archive,
                initial.worker, initial.stage, initial.size, initial.entries, initial.deadline,
                initial.deadline, **self._identity_fields())
            if scope != expected:
                raise Rejected('supervisor-reinspection-scope')
            archive, lease = self._accept(channel)
            self._checkpoint('reinspect-root')
            self.session.observe(archive, lease)
            return self._reply(channel, 'root-reinspected')
        except BaseException:
            self.close()
            raise

    def _identity_fields(self) -> dict[str, int]:
        identity = self.session.physical()
        return dict(mount_id=identity.mount_id, inode=identity.inode,
                    device_major=identity.device_major, device_minor=identity.device_minor)

    def wait_readable(self, descriptor: int) -> None:
        """Maintain checks while the owning caller waits for its next operation.

        This is not background supervision: the owner must not perform blocking
        work elsewhere while physical authority is retained.
        """
        try:
            self._wait(descriptor)
        except BaseException:
            self.close()
            raise

    def finish(self) -> None:
        try:
            self._checkpoint('close-root')
            self.session.finish()
            for _ in range(1200):
                self._wait(self.session.descriptor())
                if self.session.receive():
                    return
            raise Rejected('supervisor-close-budget')
        finally:
            self.close()

    def close(self) -> None:
        self.closed = True
        failures: list[BaseException] = []
        # End the effect path first. Observer close can wait up to five seconds.
        for release in (self.session.abort, *(c.close for c in self.channels), self.consent.close, self.operator.close):
            try:
                release()
            except BaseException as error:
                failures.append(error)
        self.channels.clear()
        if failures:
            raise BaseExceptionGroup('supervisor-cleanup-indeterminate', failures)

    def __enter__(self) -> Supervisor:
        return self

    def __exit__(self, *ignored: object) -> None:
        self.close()
