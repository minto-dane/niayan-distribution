#!/usr/bin/python3 -I
# SPDX-License-Identifier: BSD-3-Clause
"""Adopted management entry points: local artifact tools and native transport.

The root service must independently parse, plan and admit installed operations.
No command invokes another package manager or executes a shell.
"""
from __future__ import annotations

from pathlib import Path
import sys

from i18n import UI, write_text
from management_grammar import HELP as HELP, Request as Request, UsageError as UsageError, parse as parse
from management_grammar import READ_ONLY_ACTIONS

def main(command: str, argv: list[str]) -> int:
    ui = UI.from_environment()
    if command not in HELP:
        write_text(sys.stderr, ui.message('Invoke as: {commands}', commands=', '.join(HELP)) + '\n')
        return 2
    if argv == ['--help']:
        write_text(sys.stdout, HELP[command] + '\n\n' + ui.message(
            'niayan development interface; native integration is incomplete.\n'
            'Local epkg template builds and emgr -d displays are available.\n'
            'emgr_download_ifix requires provisioned authenticated repository policy.\n'
            'lslpp -l/-L query an explicitly configured native accepted catalog.\n'
            'Package changes and interactive packaging are not connected.\n'
            'Debian package names/versions are retained. Other reference-platform options are rejected.') + '\n')
        write_text(sys.stdout, ui.message('Local media indexing and listing are available through inutoc, installp and geninstall.') + '\n')
        return 0
    try:
        request = parse(command, argv)
    except UsageError as exc:
        write_text(sys.stderr, command + ': ' + ui.message(exc.message, **exc.values) + '\n' + HELP[command] + '\n')
        return 2
    if request.action in ('interim-build', 'interim-display'):
        from interim_commands import execute_local
        return execute_local(request, ui=ui)
    if request.action == 'interim-download':
        from interim_download import execute_download
        return execute_download(request, ui=ui)
    if request.action in ('index-media', 'media-list', 'media-list-colon'):
        from media import execute
        return execute(request, ui=ui)
    from management_client import execute as execute_native
    # The root receiver parses the original adopted grammar independently.
    # These client-side flags classify allowed responses, never grant effects.
    read_only = request.action in READ_ONLY_ACTIONS
    return execute_native(command, argv, ui, preview=request.preview, read_only=read_only)


if __name__ == '__main__':
    raise SystemExit(main(Path(sys.argv[0]).name, sys.argv[1:]))
