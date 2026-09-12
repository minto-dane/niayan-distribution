#!/usr/bin/python3 -I
# SPDX-License-Identifier: BSD-3-Clause
"""Nia management command grammar. Requests are untrusted, never execution grants.

Development entry points: local interim artifact construction/display work; the
native catalog/transaction service is not yet connected. No command invokes
APT, dpkg, a shell, or a privileged helper.
"""
from __future__ import annotations

from dataclasses import dataclass
import getopt
from pathlib import Path
import re
import shlex
import sys

from i18n import UI, N_, write_text


class UsageError(ValueError):
    def __init__(self, message, **values):
        self.message = message
        self.values = values
        super().__init__(message.format_map(values))


@dataclass(frozen=True)
class Request:
    command: str
    action: str
    operands: tuple[str, ...]
    flags: frozenset[str]
    values: tuple[tuple[str, str], ...]
    preview: bool = False
    attributes: tuple[tuple[str, str], ...] = ()
    delegate: Request | None = None


HELP = {
    'installp': (
        'installp {-a [-c] | -c | -r | -u} [-p] [-g] [-v] [-q]\n'
        '         [-d SOURCE] {PACKAGE [VERSION] ... | -f LIST | all}\n'
        'installp {-l | -L} -d SOURCE\n'
        'installp -s [PACKAGE ... | all]\n'
        'installp -C'),
    'lslpp': 'lslpp {-l | -L | -h | -f | -p | -d | -w} [-c] [-q] [PATTERN ...]',
    'lppchk': 'lppchk {-c | -f | -l | -v} [-m 1|2|3] [PACKAGE [FILE ...]]',
    'install_all_updates': 'install_all_updates -d SOURCE [-p] [-c] [-n] [-v] [-Y]',
    'instfix': 'instfix {-i [-c] [-q] [-v] [-F] | -p | -T} [-k "FIX ..."] [-d SOURCE]',
    'inutoc': 'inutoc [DIRECTORY]',
    'geninstall': ('geninstall -d SOURCE [-p] [-I "INSTALLP_FLAGS"] {PACKAGE ... | -f LIST | all}\n'
                   'geninstall -u {PACKAGE ... | -f LIST}\n'
                   'geninstall -L -d SOURCE'),
    'suma': ('suma {-x [-w] | -w | -s "MIN HOUR DAY MONTH WEEKDAY"} [-a FIELD=VALUE]... [TASK]\n'
             'suma -l [TASK ...]\nsuma {-u | -d} TASK\nsuma {-c | -D}'),
    'lppmgr': 'lppmgr -d SOURCE [-r | -m DIRECTORY] [-l] [-u] [-b] [-x] [-p] [-t] [-s] [-V]',
    'epkg': 'epkg [-w WORK_DIRECTORY] [-e CONTROL_FILE] LABEL',
    'emgr_download_ifix': 'emgr_download_ifix -L URL [-P DIRECTORY]',
    'emgr': ('emgr -d [-v 1|2|3] {-e PACKAGE_FILE | PACKAGE_FILE}\n'
             'emgr {-l | -c} [-L LABEL | -n NUMBER | -u VUID] [-v 1|2|3]\n'
             'emgr -r {-L LABEL | -n NUMBER | -u VUID} [-p] [-q]\n'
             'emgr -e PACKAGE_FILE [-p] [-q]\nemgr -P [PACKAGE]'),
}

SPECS = {
    'installp': 'acruClLspgvqd:f:',
    'lslpp': 'lLhfpdwcq',
    'lppchk': 'cflvm:',
    'install_all_updates': 'd:pcnvY',
    'instfix': 'icqvFpTk:d:',
    'inutoc': '',
    'geninstall': 'd:I:puf:L',
    'suma': 'xws:a:lcDud',
    'lppmgr': 'd:rm:lubxptsV',
    'epkg': 'w:e:',
    'emgr_download_ifix': 'L:P:',
    'emgr': 'de:lcrPL:n:u:v:pq',
}


def check_schedule(value: str):
    fields = value.split()
    bounds = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
    if len(fields) != 5:
        raise UsageError('schedule needs five cron fields')
    for field, (low, high) in zip(fields, bounds):
        for item in field.split(','):
            match = re.fullmatch(r'(\*|[0-9]{1,2}(?:-[0-9]{1,2})?)(?:/([0-9]{1,2}))?', item)
            if not match:
                raise UsageError('unsupported cron field')
            base, step = match.groups()
            if step is not None and not 1 <= int(step) <= high - low + 1:
                raise UsageError('cron step out of range')
            if base != '*':
                ends = [int(n) for n in base.split('-')]
                if not all(low <= n <= high for n in ends) or ends[0] > ends[-1]:
                    raise UsageError('cron field out of range')


def parse(command: str, argv: list[str]) -> Request:
    """Parse the documented subset without reading operand paths or changing state.

    Package selectors/versions and file lists remain literal, untrusted input;
    only the authenticated native resolver may expand or validate them.
    """
    if command not in SPECS:
        raise UsageError('unknown package command')
    if len(argv) > 4096 or sum(len(a) for a in argv) > 65536:
        raise UsageError('command input limit exceeded')
    if any(not a or any(ord(c) < 32 or ord(c) == 127 for c in a) for a in argv):
        raise UsageError('empty argument or control character')
    try:
        options, operands = getopt.getopt(argv, SPECS[command])
    except getopt.GetoptError as exc:
        raise UsageError('Invalid command option: {option}.', option=exc.opt) from exc
    flags: set[str] = set()
    values: dict[str, str] = {}
    attributes: dict[str, str] = {}
    for option, value in options:
        key = option[1:]
        if command == 'suma' and key == 'a':
            name, separator, content = value.partition('=')
            if not separator or name in attributes or name not in {
                'Action', 'RqType', 'DLTarget', 'DisplayName',
            }:
                raise UsageError('unknown, duplicate or malformed SUMA attribute')
            attributes[name] = content
            continue
        if key + ':' in SPECS[command]:
            if key in values:
                raise UsageError('repeated -{option}', option=key)
            if not value or (value.startswith('-') and key != 'I' and not (key == 'f' and value == '-')):
                raise UsageError('missing or unsupported value for -{option}', option=key)
            values[key] = value
        else:
            flags.add(key)
    # Do not accidentally turn a trailing option into a package selection.
    if any(a.startswith('-') for a in operands):
        raise UsageError('options must precede operands; leading-dash operands are unsupported')

    def require(condition: bool, message: str, **values):
        if not condition:
            raise UsageError(message, **values)

    def only(allowed: str):
        require((flags | values.keys()) <= set(allowed), N_('option is not valid for this action'))

    def one(choices: str) -> str:
        selected = flags & set(choices)
        require(len(selected) == 1, N_('specify exactly one action from {actions}'), actions='-' + ', -'.join(choices))
        return next(iter(selected))

    preview = False
    delegate = None
    if command == 'installp':
        actions = flags & set('acruClLs')
        if not actions:
            actions = {'a'}
        require(len(actions) == 1 or actions == {'a', 'c'}, N_('conflicting installp actions'))
        key = 'ac' if actions == {'a', 'c'} else next(iter(actions))
        action = {'a': 'apply', 'ac': 'apply-commit', 'c': 'commit', 'r': 'reject',
                  'u': 'remove', 'C': 'recover', 'l': 'media-list',
                  'L': 'media-list-colon', 's': 'applied-list'}[key]
        if key in ('a', 'ac', 'c', 'r', 'u'):
            only(key + 'pgvqf' + ('d' if 'a' in key else ''))
            require(bool(operands) != ('f' in values), N_('specify operands or -f LIST'))
            require('all' not in operands or operands == ['all'], N_('all cannot be combined with names'))
            if key in ('r', 'u'):
                require('all' not in operands, N_('name packages explicitly for reject/remove'))
            if 'a' in key:
                require('d' in values, N_('Nia requires an explicit -d SOURCE for apply'))
            preview = 'p' in flags
        elif key in ('l', 'L'):
            only(key + 'dq')
            require('d' in values and not operands, N_('media listing requires -d SOURCE and no operands'))
        elif key == 'C':
            only('C')
            require(not operands, N_('recovery covers the interrupted transaction; no operands allowed'))
        else:
            only('s')
            require('all' not in operands or operands == ['all'], N_('all cannot be combined with names'))
    elif command == 'lslpp':
        key = one('lLhfpdw')
        only(key + 'cq')
        action = {'l': 'installed-list', 'L': 'installed-summary', 'h': 'history',
                  'f': 'files', 'p': 'requisites', 'd': 'dependents', 'w': 'owners'}[key]
    elif command == 'lppchk':
        key = one('cflv')
        only(key + 'm')
        require(values.get('m', '1') in ('1', '2', '3'), N_('-m must be 1, 2 or 3'))
        require(key != 'v' or len(operands) <= 1, N_('-v does not accept file operands'))
        action = {'c': 'check-content', 'f': 'check-size', 'l': 'check-links',
                  'v': 'check-consistency'}[key]
    elif command == 'install_all_updates':
        require('d' in values and not operands, N_('specify -d SOURCE, without package operands'))
        action = 'update-installed-commit' if 'c' in flags else 'update-installed'
        preview = 'p' in flags
    elif command == 'instfix':
        key = one('ipT')
        require(not operands, N_('use -k for fix keywords'))
        if key == 'i':
            only('icqvFk')
            action = 'fix-status'
        else:
            only(key + ('kd' if key == 'p' else 'd'))
            require('d' in values, N_('specify -d SOURCE'))
            require(key != 'p' or 'k' in values, N_('-p requires -k FIX'))
            action = 'fix-packages' if key == 'p' else 'media-fixes'
        if 'k' in values:
            require(bool(values['k'].split()), N_('empty fix keyword list'))
    elif command == 'inutoc':
        require(len(operands) <= 1, N_('inutoc accepts at most one directory'))
        if not operands:
            operands = ['/usr/sys/inst.images']
        action = 'index-media'
    elif command == 'geninstall':
        require(not {'u', 'L'} <= flags, N_('conflicting geninstall actions'))
        if 'L' in flags:
            only('Ld')
            delegate = parse('installp', ['-L', '-d', values.get('d', '')] + operands)
        elif 'u' in flags:
            only('uf')
            delegate = parse('installp', ['-u'] + (['-f', values['f']] if 'f' in values else []) + operands)
        else:
            require('d' in values, N_('specify -d SOURCE'))
            try:
                nested, remainder = getopt.getopt(shlex.split(values.get('I', '-a')), 'acgpvq')
            except (getopt.GetoptError, ValueError) as exc:
                raise UsageError('unsupported installp flags in -I') from exc
            require(not remainder, N_('-I accepts only installp option flags'))
            args = [option for option, _ in nested]
            require('-a' in args or '-c' not in args, N_('geninstall -I must select apply, not commit alone'))
            if 'p' in flags:
                args.append('-p')
            delegate = parse('installp', args + ['-d', values['d']] +
                             (['-f', values['f']] if 'f' in values else []) + operands)
        action, preview = delegate.action, delegate.preview
    elif command == 'suma':
        require(all(re.fullmatch('[0-9]{1,20}', item) for item in operands), N_('task IDs must be numeric'))
        if flags & set('lcDud'):
            key = one('lcDud')
            only(key)
            require(not attributes, N_('attribute edits for this SUMA action are not supported'))
            require(key == 'l' or len(operands) == (1 if key in 'ud' else 0), N_('incorrect task ID count'))
            action = {'l': 'fetch-task-list', 'c': 'fetch-config', 'D': 'fetch-defaults',
                      'u': 'fetch-task-unschedule', 'd': 'fetch-task-delete'}[key]
        else:
            require(len(operands) <= 1, N_('at most one task ID'))
            require(bool(flags & set('xw')) or 's' in values, N_('specify -x, -w or -s'))
            require('s' not in values or not flags, N_('-s cannot be combined with -x or -w'))
            if 's' in values:
                check_schedule(values['s'])
            require(attributes.get('RqType', 'Latest') == 'Latest', N_('Foreign TL/SP/ML/PTF are not Nia release identifiers'))
            require(attributes.get('Action', 'Download') in ('Download', 'Preview', 'Metadata'),
                    N_('unsupported SUMA Action'))
            if 'DLTarget' in attributes:
                require(attributes['DLTarget'].startswith('/'), N_('DLTarget must be absolute'))
            action = ('fetch-task-schedule' if 's' in values else
                      'fetch-task-run-save' if flags == {'x', 'w'} else
                      'fetch-task-run' if 'x' in flags else 'fetch-task-save')
            # Action=Preview describes the fetch task. Saving/scheduling that
            # task is still a mutation, so it is not a global read-only flag.
    elif command == 'emgr_download_ifix':
        require('L' in values and not operands, N_('specify -L URL, without operands'))
        action = 'interim-download'
    elif command == 'epkg':
        require(len(operands) == 1, N_('specify one interim fix label'))
        require(bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+-]{0,99}', operands[0])),
                N_('invalid interim fix label'))
        action = 'interim-build' if 'e' in values else 'interim-build-interactive'
    elif command == 'emgr':
        selected = flags & set('dlcrP')
        require(len(selected) <= 1, N_('conflicting interim actions'))
        key = next(iter(selected)) if selected else 'e'
        if key == 'd':
            only('dev')
            require(('e' in values and not operands) or ('e' not in values and len(operands) == 1),
                    N_('specify one interim package with -e or as an operand'))
            action = 'interim-display'
        elif key in ('l', 'c', 'r'):
            only(key + 'Lnu' + ('pq' if key == 'r' else 'v'))
            count = len(values.keys() & set('Lnu'))
            require(not operands and (count == 1 if key == 'r' else count <= 1),
                    N_('specify one selector for remove, at most one for list/check'))
            require('n' not in values or bool(re.fullmatch(r'[1-9][0-9]{0,19}', values['n'])),
                    N_('interim number must be a positive integer'))
            action = {'l': 'interim-list', 'c': 'interim-check', 'r': 'interim-remove'}[key]
        elif key == 'P':
            only('P')
            require(len(operands) <= 1, N_('at most one package for lock display'))
            action = 'interim-locks'
        else:
            only('epq')
            require('e' in values and not operands, N_('specify -e PACKAGE_FILE'))
            action = 'interim-apply'
        require('v' not in values or values['v'] in ('1', '2', '3'), N_('verbosity must be 1, 2 or 3'))
        preview = 'p' in flags
    else:  # lppmgr
        require('d' in values and not operands, N_('specify -d SOURCE, without operands'))
        require(not ('r' in flags and 'm' in values), N_('-r and -m are mutually exclusive'))
        action = ('media-filter-list' if 'l' in flags else
                  'media-filter-remove' if 'r' in flags else
                  'media-filter-move' if 'm' in values else 'media-filter-list')
        # -p means prompt for move/remove. It is never a dry run.
    return Request(command, action, tuple(operands), frozenset(flags),
                   tuple(sorted(values.items())), preview,
                   tuple(sorted(attributes.items())), delegate)


def main(command: str, argv: list[str]) -> int:
    ui = UI.from_environment()
    if command not in HELP:
        write_text(sys.stderr, ui.message('Invoke as: {commands}', commands=', '.join(HELP)) + '\n')
        return 2
    if argv == ['--help']:
        write_text(sys.stdout, HELP[command] + '\n\n' + ui.message(
            'niayan development interface; native service is not connected.\n'
            'Local epkg template builds and emgr -d displays are available.\n'
            'emgr_download_ifix requires provisioned authenticated repository policy.\n'
            'Installed-package operations and interactive packaging are unavailable.\n'
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
    # Translation is presentation only; no fake preview or alternative writer.
    write_text(sys.stderr, ui.message(
        '{command}: {action}: native package service is not connected; no operation or preview was performed.',
        command=command, action=request.action) + '\n')
    return 1


if __name__ == '__main__':
    raise SystemExit(main(Path(sys.argv[0]).name, sys.argv[1:]))
