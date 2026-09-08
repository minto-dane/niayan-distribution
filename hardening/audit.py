#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read effective Linux mitigations or first-party ELF properties; never apply settings."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent


def load_policy(path):
    policy = json.loads(path.read_text())
    if policy['schema'] != 'org.niaos.hardening-baseline/v1':
        raise ValueError('unsupported hardening schema')
    for name, row in policy['sysctl'].items():
        if not re.fullmatch(r'[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+', name):
            raise ValueError('invalid sysctl name')
        if type(row['value']) is not int or row['value'] not in row['accepted']:
            raise ValueError('invalid sysctl value')
        if row['reference'] not in policy['references']:
            raise ValueError('missing source reference')
    return policy


def render(policy):
    return ('# SPDX-License-Identifier: MIT\n'
            '# Generated from hardening/baseline.json; see hardening/README.ja.md.\n'
            '# Administrator overrides belong in /etc/sysctl.d/90-niaos-local.conf.\n'
            + ''.join(f'{name} = {row["value"]}\n' for name, row in policy['sysctl'].items()))


def elf_properties(data):
    # Conservative ELF64 little-endian x86-64 checker. No ldd or execution.
    if len(data) < 64 or data[:7] != b'\x7fELF\x02\x01\x01':
        raise ValueError('expected ELF64 little-endian version 1')
    header = struct.unpack_from('<HHIQQQIHHHHHH', data, 16)
    kind, machine, version, _, phoff, _, _, ehsize, phsize, phnum, *_ = header
    if machine != 62 or version != 1 or ehsize != 64 or phsize != 56 or not 1 <= phnum <= 4096:
        raise ValueError('unsupported ELF header')
    if phoff < 64 or phoff + phsize * phnum > len(data):
        raise ValueError('ELF program table bounds')
    segments = []
    for n in range(phnum):
        p = struct.unpack_from('<IIQQQQQQ', data, phoff + n * phsize)
        ptype, flags, offset, _, _, size, memsize, _ = p
        if offset > len(data) or size > len(data) - offset:
            raise ValueError('ELF segment file bounds')
        if ptype == 1 and size > memsize:
            raise ValueError('ELF LOAD memory bounds')
        segments.append(p)
    stacks = [p for p in segments if p[0] == 0x6474E551]
    dynamic = [p for p in segments if p[0] == 2]
    if len(dynamic) != 1:
        raise ValueError('expected one dynamic segment')
    dp = dynamic[0]
    if dp[5] % 16:
        raise ValueError('ELF dynamic alignment')
    now = False
    terminated = False
    for offset in range(dp[2], dp[2] + dp[5], 16):
        tag, value = struct.unpack_from('<qQ', data, offset)
        if tag == 0:
            terminated = True
            break
        now |= tag == 24 or (tag == 30 and bool(value & 8)) or (tag == 0x6FFFFFFB and bool(value & 1))
    if not terminated:
        raise ValueError('unterminated dynamic table')
    result = {
        'pie': kind == 3 and sum(p[0] == 3 for p in segments) == 1,
        'non_executable_stack': len(stacks) == 1 and not bool(stacks[0][1] & 1),
        'relro': any(p[0] == 0x6474E552 and p[6] > 0 for p in segments),
        'bind_now': bool(now),
        'no_writable_executable_load': not any(p[0] == 1 and p[1] & 3 == 3 for p in segments),
    }
    return result


def runtime(policy, proc=Path('/proc'), sysroot=Path('/sys'), boot=Path('/boot'), release=None):
    rows = []

    def observe(name, read, check):
        try:
            value = read()
            passed = check(value)
            rows.append({'name': name, 'value': value, 'result': 'pass' if passed else 'fail'})
        except (OSError, ValueError) as error:
            rows.append({'name': name, 'result': 'unavailable', 'error': str(error)})

    for name, spec in policy['sysctl'].items():
        observe(name, lambda name=name: int((proc / 'sys' / name.replace('.', '/')).read_text()),
                lambda value, spec=spec: value in spec['accepted'])
    release = release or os.uname().release
    if not re.fullmatch(r'[A-Za-z0-9_.+\-]+', release):
        raise ValueError('invalid kernel release')
    config_path = boot / ('config-' + release)
    try:
        raw = config_path.read_bytes()
        config = dict(line.split('=', 1) for line in raw.decode().splitlines()
                      if line.startswith('CONFIG_') and '=' in line)
        for name in policy['kernel_config']:
            rows.append({'name': name, 'value': config.get(name),
                         'result': 'pass' if config.get(name) == 'y' else 'fail'})
        config_hash = hashlib.sha256(raw).hexdigest()
    except (OSError, UnicodeError) as error:
        rows.append({'name': 'kernel_config', 'result': 'unavailable', 'error': str(error)})
        config_hash = None
    observe('apparmor_enabled', lambda: (sysroot / 'module/apparmor/parameters/enabled').read_text().strip(),
            lambda value: value == 'Y')
    observe('apparmor_enforcing_profiles',
            lambda: sum(line.endswith(' (enforce)') for line in
                        (sysroot / 'kernel/security/apparmor/profiles').read_text().splitlines()),
            lambda value: value > 0)
    for name in policy['required_apparmor_profiles']:
        observe('apparmor_profile:' + name,
                lambda: (sysroot / 'kernel/security/apparmor/profiles').read_text().splitlines(),
                lambda value, name=name: name + ' (enforce)' in value)
    observe('boot_mitigations_not_disabled', lambda: (proc / 'cmdline').read_text().strip(),
            lambda value: not any(token in {
                'mitigations=off', 'nokaslr', 'nosmep', 'nosmap', 'noexec=off',
                'nopti', 'pti=off', 'nospectre_v1', 'nospectre_v2',
                'spectre_v2=off', 'spectre_v2_user=off', 'spec_store_bypass_disable=off',
                'mds=off', 'tsx_async_abort=off', 'l1tf=off', 'apparmor=0',
            } for token in value.split()))
    return {'kernel_release': release, 'kernel_config_sha256': config_hash, 'checks': rows,
            'result': 'pass' if all(r['result'] == 'pass' for r in rows) else 'fail',
            'scope': 'listed mitigations only; not whole-system security certification'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--policy', type=Path, default=HERE / 'baseline.json')
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--render-sysctl', action='store_true')
    mode.add_argument('--runtime', action='store_true')
    mode.add_argument('--elf', type=Path, nargs='+')
    args = ap.parse_args()
    policy = load_policy(args.policy)
    if args.render_sysctl:
        print(render(policy), end='')
        return
    if args.runtime:
        report = runtime(policy)
    else:
        rows = []
        for path in args.elf:
            with path.open('rb') as stream:
                data = stream.read(256 * 1024**2 + 1)
            if len(data) > 256 * 1024**2:
                raise ValueError('ELF observation size limit')
            properties = elf_properties(data)
            rows.append({'name': path.name, 'sha256': hashlib.sha256(data).hexdigest(),
                         'properties': properties, 'result': 'pass' if all(properties.values()) else 'fail'})
        report = {'checks': rows, 'result': 'pass' if all(r['result'] == 'pass' for r in rows) else 'fail',
                  'scope': 'ELF program headers/dynamic flags only; no compiler instrumentation proof'}
    report['schema'] = 'org.niaos.hardening-observation/v1'
    report['policy_sha256'] = hashlib.sha256(args.policy.read_bytes()).hexdigest()
    report['tool_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['result'] == 'pass' else 1)


if __name__ == '__main__':
    main()
