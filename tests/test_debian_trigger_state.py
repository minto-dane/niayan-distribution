# SPDX-License-Identifier: BSD-3-Clause
"""Reference lifecycle cases: retrigger, package waits and exact attempt replay."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from nia_common import Invalid, canonical, sha
from debian_triggers import Delivery, parse, state_activations, file_activations, route
from debian_trigger_state import State, Running, activate, start, attempt, observe_success, encode, decode

A, B, C, SCOPE = (str(n) * 64 for n in range(1, 5))


class TriggerStateTests(unittest.TestCase):
    def initial(self):
        return activate(State(SCOPE), (Delivery(B, 'cache', A, True),))

    def test_package_without_scripts_reaches_pending_and_awaited_through_real_router(self):
        interests = {B: parse(b'interest-await /usr/share/cache\n')}
        events = file_activations(A, ('usr/share/cache/file',), interests)
        state = activate(State(SCOPE), route(events, interests))
        self.assertEqual(state.pending, ((B, '/usr/share/cache'),))
        self.assertEqual(state.awaited, ((A, B),))
        self.assertFalse(json.loads(encode(state))['execution_permit'])

    def test_normal_completion_releases_awaiters_only_after_handler(self):
        state = self.initial()
        running = start(state, B)
        self.assertEqual(running.pending, ())
        self.assertEqual(running.awaited, ((A, B),))
        self.assertEqual(running.running.names, ('cache',))
        done = observe_success(running, attempt(running))
        self.assertEqual((done.pending, done.awaited, done.running), ((), (), None))
        self.assertEqual(done.revision, 3)

    def test_same_name_retrigger_during_handler_is_not_lost(self):
        running = start(self.initial(), B)
        token = attempt(running)
        again = activate(running, (Delivery(B, 'cache', A, True),))
        self.assertEqual(attempt(again), token)
        next_state = observe_success(again, token)
        self.assertEqual(next_state.pending, ((B, 'cache'),))
        self.assertEqual(next_state.awaited, ((A, B),))
        next_batch = start(next_state, B)
        self.assertNotEqual(attempt(next_batch), token)
        self.assertRaises(Invalid, observe_success, next_batch, token)
        done = observe_success(next_batch, attempt(next_batch))
        self.assertEqual((done.pending, done.awaited), ((), ()))

    def test_new_noawait_trigger_does_not_release_old_package_waiters(self):
        running = start(self.initial(), B)
        again = activate(running, (Delivery(B, 'different', C, False),))
        next_state = observe_success(again, attempt(again))
        self.assertEqual(next_state.pending, ((B, 'different'),))
        self.assertEqual(next_state.awaited, ((A, B),))
        done = start(next_state, B)
        done = observe_success(done, attempt(done))
        self.assertEqual(done.awaited, ())

    def test_completion_does_not_release_other_receiver(self):
        state = activate(self.initial(), (Delivery(C, 'other', A, True),))
        first = start(state, B)
        done = observe_success(first, attempt(first))
        self.assertEqual(done.pending, ((C, 'other'),))
        self.assertEqual(done.awaited, ((A, C),))

    def test_receiver_awaiting_another_package_retains_its_own_waiters(self):
        state = activate(self.initial(), (Delivery(C, 'other', B, True),))
        first = start(state, B)
        done = observe_success(first, attempt(first))
        self.assertEqual(done.pending, ((C, 'other'),))
        self.assertEqual(done.awaited, ((A, B), (B, C)))
        final = start(done, C)
        final = observe_success(final, attempt(final))
        self.assertEqual((final.pending, final.awaited), ((), ()))

    def test_wait_cycles_are_preserved_and_never_reported_as_completed(self):
        state = activate(State(SCOPE), (Delivery(B, 'one', A, True), Delivery(A, 'two', B, True)))
        for receiver in (A, B):
            state = start(state, receiver)
            state = observe_success(state, attempt(state))
        self.assertEqual(state.pending, ())
        self.assertEqual(state.awaited, ((A, B), (B, A)))
        raw = encode(state)
        self.assertEqual(decode(raw, SCOPE, sha(raw)), state)

    def test_duplicate_activation_coalesces_and_cannot_erase_await(self):
        state = self.initial()
        self.assertEqual(activate(state, (Delivery(B, 'cache', A, False),)), state)
        self.assertEqual(activate(state, (Delivery(B, 'cache', A, True),)), state)
        self.assertEqual(activate(state, ()), state)

    def test_recovery_preserves_running_and_does_not_restart_unknown_result(self):
        running = start(self.initial(), B)
        raw = encode(running)
        recovered = decode(raw, SCOPE, sha(raw))
        self.assertEqual(recovered, running)
        self.assertEqual(attempt(recovered), attempt(running))
        self.assertRaises(Invalid, start, recovered, B)
        self.assertEqual(recovered.awaited, ((A, B),))
        self.assertRaises(Invalid, observe_success, recovered, sha(b'wrong attempt'))
        self.assertEqual(encode(recovered), raw)

    def test_wrong_scope_changed_bytes_and_noncanonical_checkpoint_are_rejected(self):
        raw = encode(start(self.initial(), B))
        self.assertRaises(Invalid, decode, raw, A, sha(raw))
        self.assertRaises(Invalid, decode, raw + b' ', SCOPE, sha(raw))
        self.assertRaises(Invalid, decode, raw + b' ', SCOPE, sha(raw + b' '))
        value = json.loads(raw)
        value['execution_permit'] = True
        fake = canonical(value)
        self.assertRaises(Invalid, decode, fake, SCOPE, sha(fake))
        value['execution_permit'] = False
        value['unknown'] = []
        fake = canonical(value)
        self.assertRaises(Invalid, decode, fake, SCOPE, sha(fake))

    def test_invalid_state_relations_and_revisions_are_rejected(self):
        self.assertRaises(Invalid, State, SCOPE, 1, (), ((A, B),))
        self.assertRaises(Invalid, State, SCOPE, 0, ((B, 'cache'),))
        self.assertRaises(Invalid, State, SCOPE, True)
        self.assertRaises(Invalid, State, SCOPE, 1, ((B, 'cache'),), ((B, B),))
        self.assertRaises(Invalid, State, SCOPE, 1, ((B, 'cache'), (B, 'cache')))
        self.assertRaises(Invalid, State, SCOPE, 1, (), (), Running(B, ('cache',), 2))
        self.assertRaises(Invalid, activate, State(SCOPE, 2**63 - 1), ())
        self.assertRaises(Invalid, start, State(SCOPE), B)
        self.assertRaises(Invalid, observe_success, State(SCOPE), A)

    def test_limits_refuse_without_changing_input_state(self):
        state = self.initial()
        before = encode(state)
        with patch('debian_trigger_state.MAX_STATE_BYTES', 512):
            self.assertRaises(Invalid, activate, state, (Delivery(C, 'more', A, True),))
        with patch('debian_trigger_state.MAX_EVENTS', 1):
            self.assertRaises(Invalid, activate, state, (Delivery(C, 'more', A, True),))
        self.assertEqual(encode(state), before)

    def test_old_and_new_unpack_declarations_form_one_frozen_batch(self):
        interests = {B: parse(b'interest old\ninterest new\n')}
        events = state_activations(A, 'unpack', parse(b'activate old\n'), parse(b'activate new\n'))
        state = start(activate(State(SCOPE), route(events, interests)), B)
        self.assertEqual(state.running.names, ('new', 'old'))
        self.assertEqual(state.awaited, ((A, B),))


if __name__ == '__main__':
    unittest.main()
