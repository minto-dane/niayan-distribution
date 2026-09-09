# SPDX-License-Identifier: MIT
"""Report Debian target coverage; an English fallback is not a translation.

The full-language release gate fails while any target has no complete catalog.
This does not qualify fonts, shaping, input methods or translation quality.
"""
import argparse
import json
from pathlib import Path

from i18n import C_LOCALES, catalog_candidates
from i18n_catalogs import check

ROOT = Path(__file__).resolve().parent


def coverage():
    targets = json.loads((ROOT / 'debian-languages.json').read_text())
    if targets['schema'] != 'org.niaos.debian-language-targets/v1' or targets['release'] != 'trixie':
        raise ValueError('unsupported language target inventory')
    available = {path.stem for path in (ROOT / 'po').glob('*.po')}
    requests = ([dict(origin='glibc', requested=row['locale'], encoding=row['encoding']) for row in targets['glibc']]
                + [dict(origin='installer', requested=row['locale'], language=row['language']) for row in targets['installer']])
    rows = []
    for row in requests:
        candidates = catalog_candidates(row['requested'])
        if not candidates:
            raise ValueError('unsupported declared Debian locale: ' + row['requested'])
        found = next((key for key in candidates if key == 'en' or key in available), None)
        state = 'source-language' if found == 'en' else 'translated' if found else 'english-fallback'
        rows.append(dict(row, candidates=list(candidates), catalog=found or 'en', state=state))
    missing = sorted({row['candidates'][0] for row in rows if row['state'] == 'english-fallback'})
    return dict(schema='org.niaos.language-coverage/v1', release='trixie',
        glibc_locale_encoding_pairs=len(targets['glibc']), installer_choices=len(targets['installer']),
        complete_catalogs=sorted(available), source_language='en',
        all_targets_translated=not missing, missing_locale_targets=missing,
        graphical_and_input_qualification=False, rows=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-all', action='store_true')
    args = parser.parse_args()
    # Completeness is based on fully checked source/PO/MO inputs, not filenames.
    import contextlib
    import sys
    with contextlib.redirect_stdout(sys.stderr):
        check()
    result = coverage()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    if args.require_all and not result['all_targets_translated']:
        print('Full-language release gate: translations are incomplete.', file=sys.stderr)
        raise SystemExit(1)
