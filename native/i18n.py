# SPDX-License-Identifier: BSD-3-Clause
"""Per-invocation gettext presentation; never changes parser or process locale.

Only bundled catalogs are loaded. Language is a display preference, never part
of a signed request, a package identity, authorization or transaction outcome.
"""
from __future__ import annotations

import gettext
import io
import os
from pathlib import Path
import re
import struct
from string import Formatter
import unicodedata

DOMAIN = 'nia-management'
LOCALE_DIR = Path(__file__).resolve().parent / 'locale'
LOCALE = re.compile(r'(?P<language>[a-z]{2,3})(?:_(?P<territory>[A-Z]{2}|[0-9]{3}))?'
                    r'(?:\.(?P<encoding>[A-Za-z0-9-]{1,20}))?(?:@(?P<modifier>[a-z0-9-]{1,20}))?\Z')
C_LOCALES = frozenset(('C', 'POSIX', 'C.UTF-8', 'C.utf8'))


def catalog_candidates(value: str) -> tuple[str, ...]:
    """Preserve territory and script/variant modifiers; ignore only encoding.

    A requested writing system must not silently fall back to a different one.
    @euro is a monetary variant and may reuse its language's message catalog.
    Chinese regional catalogs have explicit writing-system-compatible fallbacks.
    """
    if value in C_LOCALES:
        return ('en',)
    match = LOCALE.fullmatch(value)
    if match is None:
        return ()
    language, territory, _, modifier = match.groups()
    base = language + ('_' + territory if territory else '')
    result = []
    if modifier:
        result.extend((base + '@' + modifier, language + '@' + modifier))
        if modifier != 'euro':
            return tuple(dict.fromkeys(result))
    result.append(base)
    if language == 'zh' and territory:
        if territory in ('HK', 'MO', 'TW'):
            result.append('zh_TW')
        elif territory in ('CN', 'SG'):
            result.append('zh_CN')
    else:
        result.append(language)
    return tuple(dict.fromkeys(result))


def N_(message: str) -> str:
    """Mark a literal for extraction without translating domain-layer values."""
    return message


def languages(environment) -> tuple[str, ...]:
    selected = next((environment.get(k) for k in ('LC_ALL', 'LC_MESSAGES', 'LANG') if environment.get(k)), 'C')
    # The C family provides deterministic English diagnostics for scripts.
    if selected in C_LOCALES or not LOCALE.fullmatch(selected):
        return ('en',)
    preference = environment.get('LANGUAGE', '')
    if len(preference) > 1024 or len(preference.split(':')) > 16:
        return ('en',)
    choices = [p for p in preference.split(':') if p] if preference else []
    choices.append(selected)
    result = []
    for choice in choices:
        if choice in C_LOCALES:
            result.append('en')
            break
        # Fixed safe components only; no aliases or locale paths from the host.
        for item in catalog_candidates(choice):
            if item not in result:
                result.append(item)
        if 'en' in result:
            break
    if 'en' not in result:
        result.append('en')
    return tuple(result)


def placeholders(message: str) -> frozenset[str]:
    result = set()
    for _, field, spec, conversion in Formatter().parse(message):
        if field is not None:
            if not re.fullmatch('[a-z][a-z0-9_]*', field) or spec or conversion:
                raise ValueError('translations require simple named placeholders')
            result.add(field)
    return frozenset(result)


def display_text(value) -> str:
    # Preserve joining controls used by natural languages and emoji. Escape
    # terminal controls, bidi overrides/isolates and invalid Unicode scalars.
    return ''.join(('\\u%04x' % ord(c)) if unicodedata.category(c).startswith('C')
                   and c not in ('\u200c', '\u200d') else c for c in str(value))


def write_text(stream, text: str) -> None:
    # Do not reconfigure a process-global stream. Old terminals get visible
    # escapes, never a UnicodeEncodeError after an operation already succeeded.
    encoding = getattr(stream, 'encoding', None) or 'utf-8'
    stream.write(text.encode(encoding, errors='backslashreplace').decode(encoding))


class UI:
    def __init__(self, translation=None):
        self.translation = translation or gettext.NullTranslations()

    @classmethod
    def from_environment(cls, environment=None):
        translation = None
        for language in languages(os.environ if environment is None else environment):
            if language == 'en':
                break
            path = LOCALE_DIR / language / 'LC_MESSAGES' / (DOMAIN + '.mo')
            try:
                # Do not use TEXTDOMAINDIR, LOCPATH, cwd or a caller-provided path.
                with path.open('rb') as source:
                    raw = source.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    continue
                loaded = gettext.GNUTranslations(io.BytesIO(raw))
            except (OSError, ValueError, EOFError, UnicodeError, LookupError, struct.error):
                continue
            if translation is None:
                translation = loaded
            else:
                translation.add_fallback(loaded)
        return cls(translation)

    def _format(self, source, translated, values):
        try:
            if (placeholders(translated) != placeholders(source)
                    or any(unicodedata.category(c) in ('Cc', 'Cs', 'Cf') and c not in '\n\t\u200c\u200d'
                           for c in translated)):
                translated = source
        except ValueError:
            translated = source
        return translated.format_map({key: display_text(value) for key, value in values.items()})

    def message(self, source: str, **values) -> str:
        return self._format(source, self.translation.gettext(source), values)

    def context(self, context: str, source: str, **values) -> str:
        return self._format(source, self.translation.pgettext(context, source), values)

    def plural(self, singular: str, plural: str, count: int, **values) -> str:
        if type(count) is not int or count < 0:
            raise ValueError('plural count must be a nonnegative integer')
        source = singular if count == 1 else plural
        if placeholders(singular) != placeholders(plural):
            raise ValueError('plural placeholders differ')
        return self._format(source, self.translation.ngettext(singular, plural, count),
                            dict(values, count=count))
