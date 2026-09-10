# SPDX-License-Identifier: BSD-3-Clause
"""Trigger syntax, real DEB observation, and independently specified event cases."""
import io
import sys
import tarfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from nia_common import Invalid, sha
from debian_triggers import (Activation, Directive, Delivery, parse, state_activations,
                            file_activations, route, pending)
from deb_archive import inspect_bytes
from nia_catalog import candidate

A, B, C = ('1' * 64, '2' * 64, '3' * 64)


def deb(trigger_data):
    def tar(files):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            for path, data in files.items():
                info = tarfile.TarInfo(path)
                info.size = len(data)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(data))
        return output.getvalue()
    control = {'control': b'Package: trigger-fixture\nVersion: 1\nArchitecture: all\nDescription: isolated test\n',
               'triggers': trigger_data}
    output = b'!<arch>\n'
    for name, raw in [('debian-binary', b'2.0\n'), ('control.tar', tar(control)),
                      ('data.tar', tar({'usr/share/test': b'fixture'}))]:
        header = f'{name + "/":<16}{0:<12}{0:<6}{0:<6}{"100644":<8}{len(raw):<10}`\n'.encode('ascii')
        assert len(header) == 60
        output += header + raw + (b'\n' if len(raw) % 2 else b'')
    return output


class TriggerTests(unittest.TestCase):
    def test_six_directives_comments_whitespace_aliases(self):
        raw = b' # comment\n interest cache # note\ninterest-await cache\ninterest-noawait /usr/share/x\r\nactivate old\nactivate-await old\nactivate-noawait new\n'
        self.assertEqual(parse(raw), (Directive('activate', 'new', False), Directive('activate', 'old', True),
                                    Directive('interest', '/usr/share/x', False), Directive('interest', 'cache', True)))
        self.assertEqual(parse(b''), ())

    def test_unsupported_input_is_never_ignored_or_rewritten(self):
        for raw in (b'unknown name\n', b'interest\n', b'interest a b\n', b'interest a\x00\n',
                    b'interest /usr/../etc\n', b'interest /usr//share\n', b'interest /usr/share/\n',
                    b'interest a\ninterest-noawait a\n', b'interest \xff\n',
                    b'activate /path with spaces\n', b'interest .hidden\n', b'interest \x1b[31m\n'):
            with self.subTest(raw=raw):
                self.assertRaises(Invalid, parse, raw)
        self.assertRaises(Invalid, parse, b'#' * 8193)
        self.assertRaises(Invalid, parse, b'activate cache\n' * 4097)
        self.assertRaises(Invalid, Directive, 'activate', 'cache', 1)
        self.assertRaises(Invalid, Activation, 'cache', '0' * 64, False)

    def test_all_await_combinations_and_self_activation(self):
        for interest in ('interest', 'interest-await', 'interest-noawait'):
            for activation in ('activate', 'activate-await', 'activate-noawait'):
                with self.subTest(interest=interest, activation=activation):
                    receivers = {B: parse(f'{interest} cache\n'.encode())}
                    events = state_activations(A, 'configure', parse(f'{activation} cache\n'.encode()))
                    deliveries = route(events, receivers)
                    expected_wait = interest != 'interest-noawait' and activation != 'activate-noawait'
                    self.assertEqual(deliveries, (Delivery(B, 'cache', A, expected_wait),))
                    self.assertEqual(pending(deliveries)['awaited'], {A: [B]} if expected_wait else {})
                    own = route((Activation('cache', B, True),), receivers)
                    self.assertEqual(own, (Delivery(B, 'cache', B, False),))

    def test_unpack_activates_both_versions_and_noawait_cannot_cancel_wait(self):
        before = parse(b'activate-await cache\nactivate old\n')
        after = parse(b'activate-noawait cache\nactivate-noawait new\n')
        self.assertEqual(state_activations(A, 'unpack', before, after),
                         (Activation('cache', A, True), Activation('new', A, False), Activation('old', A, True)))
        self.assertEqual(state_activations(A, 'unpack', (), after),
                         (Activation('cache', A, False), Activation('new', A, False)))

    def test_every_declared_lifecycle_boundary_and_nonactivating_completion(self):
        declared = parse(b'activate-await cache\ninterest other\n')
        for operation in ('unpack', 'configure', 'remove', 'purge', 'deconfigure', 'disappear'):
            with self.subTest(operation=operation):
                self.assertEqual(state_activations(A, operation, declared), (Activation('cache', A, True),))
        for operation in ('process-triggers', 'finish-awaited'):
            self.assertEqual(state_activations(A, operation, declared), ())
        self.assertRaises(Invalid, state_activations, A, 'invented', declared)
        self.assertRaises(Invalid, state_activations, A, 'configure', declared, declared)

    def test_file_trigger_component_prefixes_and_no_symlink_resolution(self):
        interests = {B: parse(b'interest-await /usr/share/cache\ninterest-noawait /lib/hooks\n'),
                     C: parse(b'interest-noawait /usr/share/cache/file\n')}
        paths = ('usr/share/cache/file', 'usr/share/cache/file/more', 'usr/share/cache-other/file', 'usr/lib/hooks/file')
        activations = file_activations(A, paths, interests)
        self.assertEqual(activations, (Activation('/usr/share/cache', A, True),
                                      Activation('/usr/share/cache/file', A, True)))
        self.assertEqual(file_activations(A, ('usr/share/cache-other/file',), interests), ())
        self.assertEqual(file_activations(A, ('usr/lib/hooks/file',), interests), ())
        self.assertEqual(file_activations(A, ('lib/hooks/file',), interests), (Activation('/lib/hooks', A, True),))
        self.assertRaises(Invalid, file_activations, A, ('../usr/share/cache',), interests)
        self.assertRaises(Invalid, file_activations, A, ('/usr/share/cache',), interests)

    def test_package_without_scripts_or_declarations_still_triggers_other_package(self):
        interests = {B: parse(b'interest-noawait /usr/share/icons\n')}
        events = file_activations(A, ('usr/share/icons/example/icon.png',), interests)
        self.assertEqual(pending(route(events, interests)),
                         dict(pending={B: ['/usr/share/icons']}, awaited={}, handlers_executed=False, execution_permit=False))

    def test_file_batch_depth_and_total_size_boundaries(self):
        interests = {B: parse(b'interest-noawait /\n')}
        self.assertEqual(file_activations(A, ('/'.join(['x'] * 64),), interests),
                         (Activation('/', A, True),))
        self.assertRaises(Invalid, file_activations, A, ('/'.join(['x'] * 65),), interests)
        path = '/'.join(['x' * 255] * 16) + 'x'
        self.assertEqual(len(path.encode('utf-8')), 4096)
        self.assertEqual(file_activations(A, (path,) * 4096, interests),
                         (Activation('/', A, True),))
        self.assertRaises(Invalid, file_activations, A, (path,) * 4097, interests)

    def test_batch_coalescing_and_waiting_on_packages_not_trigger_names(self):
        interests = {B: parse(b'interest cache\ninterest other\n'), C: parse(b'interest-noawait cache\n')}
        events = (Activation('cache', A, False), Activation('cache', A, True), Activation('other', A, True))
        view = pending(route(events, interests))
        self.assertEqual(view['pending'], {B: ['cache', 'other'], C: ['cache']})
        self.assertEqual(view['awaited'], {A: [B]})
        self.assertFalse(view['handlers_executed'])
        self.assertFalse(view['execution_permit'])
        self.assertEqual(route((Activation('unregistered', A, True),), interests), ())

    def test_directly_constructed_conflicting_declarations_are_rejected(self):
        declarations = (Directive('interest', 'cache', True), Directive('interest', 'cache', False))
        self.assertRaises(Invalid, route, (), {B: declarations})
        self.assertRaises(Invalid, pending, (Delivery(A, 'cache', A, True),))
        self.assertRaises(Invalid, route, (dict(name='cache'),), {})

    def test_deb_reader_preserves_raw_hashes_and_routes_metadata_to_candidate(self):
        raw_triggers = b'interest-noawait /usr/share/cache\nactivate-await cache\n'
        original = deb(raw_triggers)
        observed = inspect_bytes(original)
        declarations = [{'kind': 'activate', 'name': 'cache', 'await_completion': True},
                        {'kind': 'interest', 'name': '/usr/share/cache', 'await_completion': False}]
        self.assertEqual(observed['trigger_declarations'], declarations)
        self.assertEqual(observed['effect_members'], [{'member': 'triggers', 'sha256': sha(raw_triggers)}])
        self.assertEqual(observed['artifact_sha256'], sha(original))
        result = candidate([observed], ['trigger-fixture'], A)
        self.assertEqual(result['catalog']['artifacts'][sha(original)]['trigger_declarations'], declarations)
        self.assertFalse(result['catalog']['effects_closed'])
        self.assertFalse(result['execution_permit'])
        self.assertRaises(Invalid, inspect_bytes, deb(b'unsupported-action cache\n'))


if __name__ == '__main__':
    unittest.main()
