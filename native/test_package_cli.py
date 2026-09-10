# SPDX-License-Identifier: BSD-3-Clause
"""Public command semantics, invalid combinations, and real entry-point behavior."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from package_cli import HELP, UsageError, main, parse


class Commands(unittest.TestCase):
    def test_grouped_flags_and_attached_source(self):
        a = parse('installp', ['-acgpd/media', 'libc6', '2:2.41-12+deb13u1'])
        b = parse('installp', ['-a', '-c', '-g', '-p', '-d', '/media',
                               'libc6', '2:2.41-12+deb13u1'])
        self.assertEqual(a, b)
        self.assertEqual(a.action, 'apply-commit')
        self.assertTrue(a.preview)
        self.assertEqual(a.operands, ('libc6', '2:2.41-12+deb13u1'))

    def test_lifecycle_is_not_collapsed(self):
        for args, expected in [(['-d', '/media', 'vim'], 'apply'),
                               (['-c', 'vim'], 'commit'),
                               (['-r', 'vim'], 'reject'),
                               (['-u', 'vim'], 'remove'),
                               (['-C'], 'recover'),
                               (['-s'], 'applied-list')]:
            with self.subTest(args=args):
                self.assertEqual(parse('installp', args).action, expected)

    def test_preview_all_mutations(self):
        for flag in ('-ap', '-acp', '-cp', '-rp', '-up'):
            args = [flag] + (['-d', '/media'] if 'a' in flag else []) + ['vim']
            with self.subTest(flag=flag):
                self.assertTrue(parse('installp', args).preview)

    def test_list_file_remains_unread_intent(self):
        for source in ('-', '/does/not/exist'):
            request = parse('installp', ['-a', '-d', '/media', '-f', source])
            self.assertEqual(dict(request.values)['f'], source)

    def test_invalid_installp_combinations(self):
        cases = [[], ['-a', 'vim'], ['-acru', '-d', '/media', 'vim'],
                 ['-r', 'all'], ['-u', 'all'], ['-C', 'vim'], ['-Cp'],
                 ['-lp', '-d', '/media'], ['-s', '-d', '/media'],
                 ['-a', '-d', '/media', '-f', '-', 'vim'],
                 ['-a', '-d', '/media', 'all', 'vim'],
                 ['-c', '-d', '/media', 'vim'], ['-l', '-d', '/media', 'vim'],
                 ['-a', '-d', '/one', '-d', '/two', 'vim'],
                 ['-a', '-d', '-p', 'vim'], ['-a', '-d', '/media', 'vim', '-p']]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(UsageError):
                parse('installp', args)

    def test_lslpp_history_and_literal_patterns(self):
        request = parse('lslpp', ['-hc', 'lib*'])
        self.assertEqual(request.action, 'history')  # -h is NOT help
        self.assertEqual(request.operands, ('lib*',))
        self.assertEqual(parse('lslpp', ['-w', '/usr/bin/vim']).action, 'owners')
        self.assertEqual(parse('lslpp', ['-Lc']).action, 'installed-summary')
        with self.assertRaises(UsageError):
            parse('lslpp', ['-lf'])

    def test_lppchk_is_read_only_and_modes_are_distinct(self):
        for flag, action in [('c', 'check-content'), ('f', 'check-size'),
                             ('l', 'check-links'), ('v', 'check-consistency')]:
            self.assertEqual(parse('lppchk', ['-' + flag]).action, action)
        for args in (['-cu'], ['-cv'], ['-v', 'vim', '/file'], ['-f', '-m', '4']):
            with self.subTest(args=args), self.assertRaises(UsageError):
                parse('lppchk', args)

    def test_update_all_is_installed_selection_not_media_all(self):
        request = parse('install_all_updates', ['-pc', '-d', '/media'])
        self.assertEqual(request.action, 'update-installed-commit')
        self.assertTrue(request.preview)
        self.assertEqual(request.operands, ())
        for args in ([], ['-d', '/media', 'all'], ['-r', '-d', '/media']):
            with self.subTest(args=args), self.assertRaises(UsageError):
                parse('install_all_updates', args)

    def test_instfix_p_lists_packages_not_installp_preview(self):
        request = parse('instfix', ['-p', '-k', 'DSA-0000-1', '-d', '/media'])
        self.assertEqual(request.action, 'fix-packages')
        self.assertFalse(request.preview)
        self.assertEqual(parse('instfix', ['-icqk', 'DSA-0000-1']).action, 'fix-status')
        for args in (['-i', '-d', '/media'], ['-ip'], ['-T', '-k', 'fix'],
                     ['-p', '-d', '/media'], ['-ik', '   ']):
            with self.subTest(args=args), self.assertRaises(UsageError):
                parse('instfix', args)

    def test_inutoc_default_and_explicit_directory(self):
        self.assertEqual(parse('inutoc', []).action, 'index-media')
        self.assertEqual(parse('inutoc', []).operands, ('/usr/sys/inst.images',))
        self.assertEqual(parse('inutoc', ['/media']).operands, ('/media',))
        with self.assertRaises(UsageError):
            parse('inutoc', ['/one', '/two'])

    def test_no_silent_compatibility_options(self):
        for args in (['-aX', '-d', '/media', 'vim'], ['-aF', '-d', '/media', 'vim'],
                     ['-aN', '-d', '/media', 'vim'], ['-R', '/', '-c', 'vim'],
                     ['--help', '-u', 'vim']):
            with self.subTest(args=args), self.assertRaises(UsageError):
                parse('installp', args)

    def test_invalid_and_bounded_input(self):
        for args in (['-l', ''], ['-l', 'vim\n'], ['-l', 'x' * 65537],
                     ['-l'] + ['x'] * 4096):
            with self.assertRaises(UsageError):
                parse('lslpp', args)

    def test_geninstall_uses_same_installp_intent(self):
        request = parse('geninstall', ['-p', '-d', '/media', '-I', '-acg', 'vim'])
        self.assertEqual(request.delegate, parse('installp', ['-acgp', '-d', '/media', 'vim']))
        self.assertTrue(request.preview)
        self.assertEqual(parse('geninstall', ['-L', '-d', '/media']).action, 'media-list-colon')
        self.assertEqual(parse('geninstall', ['-u', 'vim']).action, 'remove')
        for args in (['-uL', 'vim'], ['-d', '/media', '-I', '-r', 'vim'],
                     ['-d', '/media', '-I', '-ac; true', 'vim'],
                     ['-d', '/media', '-I', '-c', 'vim'],
                     ['-d', '/media', '-I', '-d /other', 'vim'],
                     ['-d', '/media', '-I', '-aX', 'vim']):
            with self.subTest(args=args), self.assertRaises(UsageError):
                parse('geninstall', args)

    def test_suma_task_operations_and_attributes(self):
        request = parse('suma', ['-xw', '-a', 'Action=Preview', '-a', 'RqType=Latest',
                                 '-a', 'DLTarget=/media', '-a', 'DisplayName=Weekly updates'])
        self.assertEqual(request.action, 'fetch-task-run-save')
        self.assertEqual(dict(request.attributes)['DisplayName'], 'Weekly updates')
        self.assertFalse(request.preview)  # Saving a preview task still writes state.
        self.assertEqual(parse('suma', ['-s', '0 23 * * 1', '123']).action, 'fetch-task-schedule')
        self.assertEqual(parse('suma', ['-l', '123', '124']).action, 'fetch-task-list')
        self.assertEqual(parse('suma', ['-u', '123']).action, 'fetch-task-unschedule')
        self.assertEqual(parse('suma', ['-d', '123']).action, 'fetch-task-delete')
        self.assertEqual(parse('suma', ['-D']).action, 'fetch-defaults')
        self.assertEqual(parse('suma', ['-c']).action, 'fetch-config')

    def test_suma_does_not_accept_foreign_specific_or_ambiguous_settings(self):
        for args in ([], ['-d'], ['-u', 'bad'], ['-l', '-a', 'RqType=Latest'],
                     ['-x', '-a', 'RqType=TL'], ['-x', '-a', 'FilterML=7300-02'],
                     ['-x', '-a', 'Action=Clean'], ['-x', '-a', 'DLTarget=relative'],
                     ['-x', '-a', 'RqType=Latest', '-a', 'RqType=Latest'],
                     ['-x', '-s', '0 23 * * 1'], ['-w', '-s', '0 23 * * 1'],
                     ['-c', '-a', 'FIXSERVER_PROTOCOL=http']):
            with self.subTest(args=args), self.assertRaises(UsageError):
                parse('suma', args)

    def test_suma_schedule_bounds(self):
        for schedule in ('*/15 0-23/2 1,15 * 0-6', '0 0 1 1 0'):
            self.assertEqual(parse('suma', ['-s', schedule]).action, 'fetch-task-schedule')
        for schedule in ('60 * * * *', '0 24 * * *', '0 0 0 * *', '0 0 1 13 *',
                         '0 0 * * 7', '*/0 * * * *', '5-2 * * * *', '* * * *',
                         '* * * * * /bin/true', '@reboot', '*,,1 * * * *'):
            with self.subTest(schedule=schedule), self.assertRaises(UsageError):
                parse('suma', ['-s', schedule])

    def test_lppmgr_prompt_is_not_preview_and_list_overrides_removal(self):
        request = parse('lppmgr', ['-d', '/media', '-pur'])
        self.assertEqual(request.action, 'media-filter-remove')
        self.assertFalse(request.preview)
        self.assertIn('p', request.flags)
        self.assertEqual(parse('lppmgr', ['-d', '/media', '-url']).action, 'media-filter-list')
        self.assertEqual(parse('lppmgr', ['-d', '/media', '-x', '-m', '/save']).action, 'media-filter-move')
        for args in (['-d', '/media', '-r', '-m', '/save'], ['-d', '/media', '-X'],
                     ['-d', '/media', '-k', 'ja_JP']):
            with self.subTest(args=args), self.assertRaises(UsageError):
                parse('lppmgr', args)

    def test_command_inventory_matches_actual_development_entrypoints(self):
        root = Path(__file__).resolve().parent
        catalog = json.loads((root / 'management-commands.json').read_text())
        self.assertFalse(catalog['complete_reference_inventory'])
        parsed = set()
        names = set()
        for family in catalog['families']:
            self.assertTrue(family['reference_status'])
            self.assertTrue(family['remaining'])
            for name in family['commands']:
                self.assertNotIn(name, names)
                names.add(name)
                if family['state'] in ('grammar-only', 'local-artifact-only', 'authenticated-fetch-only',
                                       'media-listing-connected-installed-operations-pending',
                                       'local-index-connected-media-retention-pending'):
                    parsed.add(name)
        self.assertEqual(parsed, set(HELP))
        self.assertEqual({p.name for p in (root / 'bin').iterdir()}, parsed)
        for name in ('smit', 'smitty', 'lssrc', 'lsdev', 'nim'):
            self.assertIn(name, names)
            self.assertFalse((root / 'bin' / name).exists())
        families = {f['name']: f for f in catalog['families']}
        for name in ('services', 'devices', 'accounts', 'storage', 'network-and-tuning'):
            self.assertEqual(families[name]['state'], 'excluded-external-system')
        self.assertEqual(families['interim-fixes']['state'], 'local-artifact-only')
        for name in ('nia', 'niactl', 'missionctl'):
            self.assertNotIn(name, names)
            self.assertFalse((root / 'bin' / name).exists())

    def test_unconnected_actions_never_report_success(self):
        for command, args in [('installp', ['-ap', '-d', '/media', 'vim']),
                              ('installp', ['-C']), ('lslpp', ['-l']),
                              ('lppchk', ['-v']), ('instfix', ['-i'])]:
            out, err = io.StringIO(), io.StringIO()
            with self.subTest(command=command), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(main(command, args), 1)
            self.assertEqual(out.getvalue(), '')
            self.assertIn('not connected', err.getvalue())

    def test_real_named_entry_points_and_no_fallback(self):
        bindir = Path(__file__).resolve().parent / 'bin'
        with tempfile.TemporaryDirectory() as tmp:
            # An empty PATH prevents a hidden dependence on any system writer.
            env = {'PATH': tmp, 'LANG': 'C.UTF-8'}
            before = os.listdir(tmp)
            for command in HELP:
                proc = subprocess.run([str(bindir / command), '--help'], cwd=tmp,
                                      env=env, capture_output=True, text=True, timeout=5)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn(command, proc.stdout)
                self.assertIn('not connected', proc.stdout)
            proc = subprocess.run([str(bindir / 'installp'), '-ac', '-d', tmp, 'vim'],
                                  cwd=tmp, env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(os.listdir(tmp), before)


if __name__ == '__main__':
    unittest.main()
