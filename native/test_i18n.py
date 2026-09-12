# SPDX-License-Identifier: BSD-3-Clause
"""Actual catalogs/CLI locale behavior and immutable operation/artifact values."""
import concurrent.futures
import gettext
import io
import json
import locale
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from i18n import UI, DOMAIN, display_text, languages, write_text, catalog_candidates
from i18n_catalogs import source_forms
from interim_commands import display
from interim_package import encode
from package_cli import HELP, parse
from test_interim_package import fixture

ROOT = Path(__file__).resolve().parent


class LocalizationTests(unittest.TestCase):
    def setUp(self):
        self.ja = UI.from_environment({'LANG': 'ja_JP.UTF-8'})
        self.en = UI.from_environment({'LANG': 'C.UTF-8'})

    def run_command(self, command, args, environment, cwd=None):
        return subprocess.run([str(ROOT / 'bin' / command), *map(str, args)],
            cwd=cwd, env={'PATH': '', 'LANG': 'C.UTF-8', **environment},
            capture_output=True, encoding='utf-8', timeout=10)

    def test_locale_precedence_and_language_list(self):
        cases = [({'LANG': 'ja_JP.UTF-8'}, 'ja_JP'),
                 ({'LANG': 'ja_JP.UTF-8', 'LC_MESSAGES': 'en_US.UTF-8'}, 'en_US'),
                 ({'LANG': 'en_US.UTF-8', 'LC_MESSAGES': 'ja_JP.UTF-8'}, 'ja_JP'),
                 ({'LANG': 'ja_JP.UTF-8', 'LC_ALL': 'en_GB.UTF-8'}, 'en_GB'),
                 ({'LANG': 'ja_JP.UTF-8', 'LC_ALL': '', 'LANGUAGE': 'fr:ja'}, 'fr'),
                 ({'LANG': 'ja_JP.UTF-8', 'LANGUAGE': 'en:ja'}, 'en')]
        for env, first in cases:
            with self.subTest(env=env):
                self.assertEqual(languages(env)[0], first)
        self.assertEqual(UI.from_environment({'LANG': 'de_DE.UTF-8', 'LANGUAGE': 'fr:ja'}).message('PACKAGE'), 'PAQUET')
        self.assertEqual(UI.from_environment({'LANG': 'ja_JP.UTF-8', 'LANGUAGE': 'en:ja'}).message('PACKAGE'), 'PACKAGE')

    def test_every_pinned_debian_locale_and_installer_choice_is_accepted(self):
        target = json.loads((ROOT / 'debian-languages.json').read_text())
        self.assertEqual(len(target['glibc']), 509)
        self.assertEqual(len(target['installer']), 78)
        for row in target['glibc'] + target['installer']:
            with self.subTest(row=row):
                self.assertTrue(catalog_candidates(row['locale']))
                self.assertTrue(UI.from_environment({'LANG': row['locale']}).message('PACKAGE'))

    def test_script_modifiers_and_chinese_writing_systems_are_not_dropped(self):
        self.assertEqual(catalog_candidates('sr_RS.UTF-8@latin'), ('sr_RS@latin', 'sr@latin'))
        self.assertEqual(catalog_candidates('ks_IN@devanagari'), ('ks_IN@devanagari', 'ks@devanagari'))
        self.assertEqual(catalog_candidates('ca_ES.UTF-8@valencia'), ('ca_ES@valencia', 'ca@valencia'))
        self.assertEqual(catalog_candidates('de_DE.ISO-8859-15@euro'), ('de_DE@euro', 'de@euro', 'de_DE', 'de'))
        self.assertEqual(catalog_candidates('zh_TW.UTF-8'), ('zh_TW',))
        self.assertEqual(catalog_candidates('zh_HK.UTF-8'), ('zh_HK', 'zh_TW'))
        self.assertEqual(catalog_candidates('zh_SG.UTF-8'), ('zh_SG', 'zh_CN'))
        self.assertEqual(catalog_candidates('eo.UTF-8'), ('eo',))
        self.assertEqual(catalog_candidates('syr'), ('syr',))

    def test_fallback_is_not_counted_as_full_language_support(self):
        from language_coverage import coverage
        report = coverage()
        self.assertFalse(report['all_targets_translated'])
        japanese = [r for r in report['rows'] if r['requested'].startswith('ja_')]
        self.assertTrue(japanese)
        self.assertTrue(all(r['state'] == 'translated' and r['catalog'] == 'ja' for r in japanese))
        unavailable = next(r for r in report['rows'] if r['requested'] == 'sr_RS@latin')
        self.assertEqual(unavailable['state'], 'english-fallback')
        self.assertIn('sr_RS@latin', report['missing_locale_targets'])
        self.assertFalse(report['graphical_and_input_qualification'])

    def test_c_locales_override_language_and_unknown_languages_fall_back(self):
        for value in ('C', 'POSIX', 'C.UTF-8', 'C.utf8'):
            ui = UI.from_environment({'LC_ALL': value, 'LANGUAGE': 'ja', 'LANG': 'ja_JP.UTF-8'})
            self.assertEqual(ui.message('PACKAGE'), 'PACKAGE')
        self.assertEqual(UI.from_environment({'LANG': 'zz_ZZ.UTF-8'}).message('PACKAGE'), 'PACKAGE')
        self.assertEqual(UI.from_environment({}).message('PACKAGE'), 'PACKAGE')

    def test_language_input_is_bounded_and_never_becomes_a_catalog_path(self):
        for bad in ('../../tmp', '/tmp/ja', 'ja\n', 'ja' * 1000):
            self.assertEqual(languages({'LANG': bad}), ('en',))
        self.assertEqual(languages({'LANG': 'ja_JP.UTF-8', 'LANGUAGE': 'ja:' * 100}), ('en',))
        with tempfile.TemporaryDirectory() as directory:
            env = {'LANG': 'ja_JP.UTF-8', 'TEXTDOMAINDIR': directory, 'LOCPATH': directory}
            result = self.run_command('installp', ['--help'], env, cwd=directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('開発用インターフェイス', result.stdout)
            self.assertEqual(os.listdir(directory), [])

    def test_bundled_catalog_covers_all_public_messages(self):
        forms = source_forms()
        for message in forms:
            with self.subTest(message=message):
                self.assertIn(message, self.ja.translation._catalog)
        self.assertEqual(self.ja.context('reboot-required', 'yes'), '必要')
        self.assertEqual(self.ja.context('unrelated-question', 'yes'), 'yes')

    def test_all_entrypoint_help_keeps_syntax_and_localizes_explanation(self):
        for command in HELP:
            with self.subTest(command=command):
                result = self.run_command(command, ['--help'], {'LC_ALL': 'ja_JP.UTF-8'})
                self.assertEqual((result.returncode, result.stderr), (0, ''))
                self.assertTrue(result.stdout.startswith(HELP[command] + '\n'))
                self.assertIn('管理サービスは未接続', result.stdout)

    def test_error_status_streams_and_dynamic_parameters_do_not_depend_on_language(self):
        for env, required in (({'LANG': 'C.UTF-8'}, 'repeated -d'),
                              ({'LANG': 'ja_JP.UTF-8'}, '-d が重複')):
            result = self.run_command('installp', ['-d', '/one', '-d', '/two', 'package'], env)
            self.assertEqual((result.returncode, result.stdout), (2, ''))
            self.assertIn(required, result.stderr)
            result = self.run_command('installp', ['-d', '/media', 'package'], env)
            self.assertEqual((result.returncode, result.stdout), (1, ''))
            self.assertIn('installp: apply:', result.stderr)

    def test_raw_operations_and_signed_artifact_bytes_do_not_change(self):
        manifest, artifacts = fixture()
        manifest['description'] = '日本語 العربية فارسی\u200c واژه 👩\u200d💻 e\u0301'
        raw = encode(manifest, artifacts)
        request = parse('installp', ['-ac', '-d', '/資料', 'sample-bin', '1:2.0-4'])
        before = (raw, request)
        for ui in (self.ja, self.en):
            text = display(raw, 3, ui=ui)
            for value in ('sample-bin', '1:2.0-4', manifest['description'], 'service-restart', 'regular'):
                self.assertIn(value, text)
        self.assertEqual((encode(manifest, artifacts), parse('installp', ['-ac', '-d', '/資料', 'sample-bin', '1:2.0-4'])), before)
        self.assertIn('緊急修正ラベル: fix001', display(raw, 1, ui=self.ja))

    def test_real_build_under_japanese_keeps_exact_original_bytes(self):
        manifest, artifacts = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = root / '制御.json'
            control.write_text(json.dumps(manifest, ensure_ascii=False))
            for digest, raw in artifacts.items():
                (root / (digest + '.deb')).write_bytes(raw)
            result = self.run_command('epkg', ['-e', control, '-w', root / '成果物', 'fix001'], {'LANG': 'ja_JP.UTF-8'})
            self.assertEqual((result.returncode, result.stderr), (0, ''))
            self.assertTrue(result.stdout.startswith('パッケージファイル: '))
            output, = (root / '成果物/fix001').glob('*.epkg')
            self.assertEqual(output.read_bytes(), encode(manifest, artifacts))
            again = self.run_command('epkg', ['-e', control, '-w', root / '成果物', 'fix001'], {'LANG': 'ja_JP.UTF-8'})
            self.assertEqual((again.returncode, again.stdout), (1, ''))
            self.assertIn('[NIA-E-EXISTS]', again.stderr)
            self.assertIn('上書きしていません', again.stderr)

    def test_untrusted_controls_escaped_and_joining_characters_preserved(self):
        value = '日本語\x1b[31m\u009b\u202eاسم\u2066\udcff\u200c\u200d'
        shown = display_text(value)
        self.assertEqual(shown, '日本語\\u001b[31m\\u009b\\u202eاسم\\u2066\\udcff\u200c\u200d')
        text = self.ja.message('Package file is: {path}', path=value)
        self.assertIn(shown, text)

    def test_ascii_terminal_and_non_tty_do_not_raise_encoding_error(self):
        data = io.BytesIO()
        stream = io.TextIOWrapper(data, encoding='ascii', errors='strict')
        write_text(stream, self.ja.message('PACKAGE') + '\n')
        stream.flush()
        self.assertEqual(data.getvalue(), 'パッケージ\n'.encode('ascii', errors='backslashreplace'))
        self.assertFalse(stream.isatty())

    def test_locale_is_not_global_and_parallel_rendering_does_not_mix_languages(self):
        before = locale.setlocale(locale.LC_ALL)
        def render(n):
            return (self.ja if n % 2 else self.en).message('PACKAGE')
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(render, range(100)))
        self.assertEqual(result, ['PACKAGE', 'パッケージ'] * 50)
        self.assertEqual(locale.setlocale(locale.LC_ALL), before)

    def test_missing_broken_and_invalid_translation_fall_back_without_changing_outcome(self):
        with patch('i18n.LOCALE_DIR', Path('/does/not/exist')):
            self.assertEqual(UI.from_environment({'LANG': 'ja'}).message('PACKAGE'), 'PACKAGE')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'ja/LC_MESSAGES' / (DOMAIN + '.mo')
            path.parent.mkdir(parents=True)
            path.write_bytes(b'broken')
            with patch('i18n.LOCALE_DIR', root):
                self.assertEqual(UI.from_environment({'LANG': 'ja'}).message('PACKAGE'), 'PACKAGE')
            compiled = (ROOT / 'locale/ja/LC_MESSAGES' / (DOMAIN + '.mo')).read_bytes()
            path.write_bytes(compiled.replace(b'charset=UTF-8', b'charset=BAD-8'))
            with patch('i18n.LOCALE_DIR', root):
                self.assertEqual(UI.from_environment({'LANG': 'ja'}).message('PACKAGE'), 'PACKAGE')
        class Broken(gettext.NullTranslations):
            def gettext(self, message):
                return '{path.__class__}'
        self.assertEqual(UI(Broken()).message('Package file is: {path}', path='ok'), 'Package file is: ok')

    def test_added_catalogs_have_complete_messages_and_language_independent_operations(self):
        labels = {'de': 'PAKET', 'es': 'PAQUETE', 'fr': 'PAQUET',
                  'ko': '패키지', 'zh_CN': '软件包', 'zh_TW': '套件'}
        for language, label in labels.items():
            with self.subTest(language=language):
                ui = UI.from_environment({'LANG': language})
                self.assertEqual(ui.message('PACKAGE'), label)
                for message in source_forms():
                    self.assertIn(message, ui.translation._catalog)
                for command in HELP:
                    result = self.run_command(command, ['--help'], {'LANG': language})
                    self.assertEqual((result.returncode, result.stderr), (0, ''))
                    self.assertTrue(result.stdout.startswith(HELP[command] + '\n'))
                    self.assertNotIn('niayan development interface', result.stdout)
                invalid = self.run_command('installp', ['-d', '/one', '-d', '/two', 'package'], {'LANG': language})
                self.assertEqual((invalid.returncode, invalid.stdout), (2, ''))
                self.assertIn('-d', invalid.stderr)
                self.assertNotIn('repeated -d', invalid.stderr)
                unavailable = self.run_command('installp', ['-d', '/media', 'package'], {'LANG': language})
                self.assertEqual((unavailable.returncode, unavailable.stdout), (1, ''))
                self.assertIn('installp', unavailable.stderr)
                self.assertIn('apply', unavailable.stderr)
                self.assertEqual(ui.message('Package file is: {path}', path='/tmp/é-資料').count('/tmp/é-資料'), 1)
        self.assertEqual(UI.from_environment({'LANG': 'zh_HK.UTF-8'}).message('PACKAGE'), '套件')
        self.assertEqual(UI.from_environment({'LANG': 'zh_SG.UTF-8'}).message('PACKAGE'), '软件包')
        self.assertEqual(UI.from_environment({'LANG': 'de_DE.ISO-8859-15@euro'}).message('PACKAGE'), 'PAKET')

    def test_real_gettext_plural_rules_support_languages_with_more_than_two_forms(self):
        # Compile an isolated synthetic catalog with three forms using the same
        # standard tooling. This is a grammar test, not a shipped translation.
        po = '''msgid ""
msgstr "Content-Type: text/plain; charset=UTF-8\\nPlural-Forms: nplurals=3; plural=(n==1 ? 0 : n==2 ? 1 : 2);\\n"

msgid "{count} item"
msgid_plural "{count} items"
msgstr[0] "single {count}"
msgstr[1] "dual {count}"
msgstr[2] "many {count}"
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'forms.po').write_text(po)
            subprocess.run(['/usr/bin/msgfmt', '--check-format', '-o', str(root / 'forms.mo'), str(root / 'forms.po')], check=True)
            with (root / 'forms.mo').open('rb') as source:
                ui = UI(gettext.GNUTranslations(source))
            self.assertEqual([ui.plural('{count} item', '{count} items', n) for n in (0, 1, 2, 5)],
                             ['many 0', 'single 1', 'dual 2', 'many 5'])
            with self.assertRaises(ValueError):
                ui.plural('{count} item', '{count} items', True)


if __name__ == '__main__':
    unittest.main()
