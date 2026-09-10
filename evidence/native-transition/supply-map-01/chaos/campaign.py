# SPDX-License-Identifier: MIT
"""Native supply map interruption campaign, confined to fresh private CAS copies."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import signal
import struct
import subprocess
import tempfile
import time

import test_archive_receipt as fixtures
from archive_receipt import scope
from deb_archive import ar_members, decompress, tar_inventory, MAX_CONTROL

HERE = Path(__file__).resolve().parent
DRIVER = HERE/'bin/map_chaos_driver'
TRACE = HERE/'strace'
NATIVE_FIXTURE = Path('/workspace/pkgcore/build/test-bin/run_supply_map_tests')
SYSCALLS = ('write', 'fsync', 'renameat2', 'pread64')
ZERO = '0'*64


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise SystemExit('isolated unprivileged test user required')
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    rng = random.Random(args.seed)
    report = {'result': 'running', 'seed': args.seed, 'cases': [], 'started_utc': time.time(),
              'driver_sha256': sha(DRIVER.read_bytes()), 'strace_sha256': sha(TRACE.read_bytes()),
              'scope': 'initial native supply map preparation/verification and retained references',
              'physical_power_loss': False, 'accepted_publication_or_boot': False}
    media = output/'public-fixture'
    media.mkdir(mode=0o700)

    def persist():
        (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')

    def object_path(store, address):
        return store/'objects'/address[:2]/address[2:]

    def state(store):
        found = {}
        for path in sorted(store.rglob('*')):
            if path.is_file():
                assert not path.is_symlink() and path.stat().st_size < 1024*1024
                found[str(path.relative_to(store))] = {'sha256': sha(path.read_bytes()), 'size': path.stat().st_size}
        return found

    def invoke(store, action, tag, injection=None, deadline=30000, trace=False):
        command = [str(DRIVER), action, str(store), str(media), str(deadline)]
        log = output/(tag+'.trace')
        if trace or injection:
            command = [str(TRACE), '-qq', '-yy', '-s', '96', '-e', 'trace='+','.join(SYSCALLS),
                       '-o', str(log), *(['-e', 'inject='+injection] if injection else []), *command]
        start = time.monotonic()
        result = subprocess.run(command, text=True, capture_output=True, timeout=40,
                                env={**os.environ, 'LD_LIBRARY_PATH': str(HERE/'lib')})
        elapsed = (time.monotonic()-start)*1000
        (output/(tag+'.log')).write_text(result.stdout+result.stderr)
        assert 'VIOLATION' not in result.stdout+result.stderr
        match = re.search(r'^RESULT (\w+) ([0-9a-f]{64})\s+(\d+)$', result.stdout, re.M)
        if match:
            assert match[2] == (expected if match[1] == 'OK' else ZERO)
            if match[1] != 'OK':
                assert int(match[3]) == 0
        return {'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr,
                'outcome': match[1] if match else None, 'ms': elapsed,
                'trace': log.read_text() if log.exists() else '', 'command': command}

    def good(result):
        assert result['returncode'] == 0 and result['outcome'] == 'OK', result

    def refuse(result):
        assert result['returncode'] in (10, 11) and result['outcome'] != 'OK'
        assert result['outcome'] or 'FAIL ' in result['stdout'], result

    def recover(store, tag):
        start = time.monotonic()
        good(invoke(store, 'prepare', tag+'-resume'))
        good(invoke(store, 'verify', tag+'-recovered'))
        assert sha(object_path(store, expected).read_bytes()) == expected
        return (time.monotonic()-start)*1000

    def record(row):
        row['result'] = 'pass'
        report['cases'].append(row)
        persist()
        print('PASS', row['id'], row['kind'], flush=True)

    def calls(raw, syscall):
        return [line for line in raw.splitlines() if line.startswith(syscall+'(')]

    with tempfile.TemporaryDirectory(prefix='nia-map-chaos-base-') as temporary:
        parent = Path(temporary)
        base = parent/'base'
        base.mkdir(mode=0o700)
        fixtures.ReceiptTests.setUpClass()
        case = fixtures.ReceiptTests()
        try:
            case.setUp()
            with case.remote.client(case.cache) as repository:
                receipt = case.issue(repository)
                expected_scope = bytes.fromhex(scope(repository, case.target))
            original = case.fixture.fixture.deb
            control = tar_inventory(decompress(*ar_members(original)[1], MAX_CONTROL), control=True)[1]['control']
            artifacts = {'receipt': receipt.wire, 'policy': receipt.policy_bytes, 'original.deb': original,
                         'control': control, 'InRelease': case.fixture.signed, 'Packages': case.fixture.fixture.packed,
                         'keyring': case.fixture.fixture.keyring, 'public-key': case.public_key, 'scope': expected_scope}
            for name, raw in artifacts.items():
                (media/name).write_bytes(raw)
            result = subprocess.run([str(NATIVE_FIXTURE), str(base), str(media), 'external'],
                                    text=True, capture_output=True, timeout=60)
            (output/'fixture.log').write_text(result.stdout+result.stderr)
            assert result.returncode == 0, result
            values = dict(line.split() for line in result.stdout.splitlines() if line.startswith('SUPPLY_'))
            expected = values['SUPPLY_MAP']
            catalog, closure = values['SUPPLY_CATALOG'], values['SUPPLY_CLOSURE']
            wire = (b'NIASMAP1'+bytes([104])*16+bytes(64)+bytes.fromhex(catalog)+bytes.fromhex(closure)
                    +struct.pack('>Q', 1)+hashlib.sha256(original).digest()+hashlib.sha256(control).digest()
                    +hashlib.sha256(receipt.wire).digest())
            assert sha(wire) == expected and object_path(base, expected).read_bytes() == wire
            artifacts['map'] = wire
            (media/'map').write_bytes(wire)
            for name in artifacts:
                (media/name).chmod(0o400)
        finally:
            case.doCleanups()
            fixtures.ReceiptTests.tearDownClass()
        hashes = {name: sha(raw) for name, raw in artifacts.items()}
        report['public_inputs'] = {name: {'sha256': hashes[name], 'size': len(raw)} for name, raw in artifacts.items()}
        report['base_objects'] = state(base)
        assert sum(row['size'] for row in report['base_objects'].values()) < 16*1024*1024
        object_path(base, expected).unlink()  # remove only this unpinned disposable candidate map
        shard = object_path(base, expected).parent
        if not any(shard.iterdir()):
            shard.rmdir()  # exercise first publication's directory creation too

        def copy_base(directory):
            store = Path(directory)/'store'
            shutil.copytree(base, store)
            return store

        persist()
        try:
            with tempfile.TemporaryDirectory(prefix='nia-map-chaos-baseline-') as temp:
                store = copy_base(temp)
                baseline = invoke(store, 'prepare', 'baseline-prepare', trace=True)
                good(baseline)
                read = invoke(store, 'verify', 'baseline-verify', trace=True)
                good(read)
            lines = baseline['trace'].splitlines()
            write_at = next(i for i, line in enumerate(lines) if line.startswith('write(') and '"NIASMAP1' in line)
            rename_at = next(i for i, line in enumerate(lines) if line.startswith('renameat2(') and expected[2:] in line)
            syncs = [i for i, line in enumerate(lines) if line.startswith('fsync(')]
            before_write = max(i for i in syncs if i < write_at)
            points = [write_at, rename_at, before_write, *[i for i in syncs if i > write_at]]
            assert len(points) in (6, 7), points
            schedule = []
            for index in points:
                line = lines[index]
                syscall = line.split('(', 1)[0]
                nth = sum(l.startswith(syscall+'(') for l in lines[:index+1])
                for kind in ('io-error', 'kill'):
                    schedule.append({'kind': kind, 'syscall': syscall, 'nth': nth, 'baseline': line})
            rng.shuffle(schedule)
            report['schedule'] = schedule
            persist()
            for i, spec in enumerate(schedule):
                tag = 'fault-%02d' % i
                with tempfile.TemporaryDirectory(prefix='nia-map-chaos-fault-') as temp:
                    store = copy_base(temp)
                    effect = 'signal=SIGKILL' if spec['kind'] == 'kill' else 'error='+('ENOSPC' if spec['syscall'] == 'write' else 'EIO')
                    injection = f"{spec['syscall']}:{effect}:when={spec['nth']}"
                    result = invoke(store, 'prepare', tag+'-fault', injection=injection)
                    hit_calls = calls(result['trace'], spec['syscall'])
                    assert len(hit_calls) >= spec['nth']
                    hit = hit_calls[spec['nth']-1]
                    assert str(store) in hit and ('/incoming' in hit or '/objects' in hit)
                    if spec['kind'] == 'kill':
                        assert result['returncode'] == -signal.SIGKILL and 'killed by SIGKILL' in result['trace']
                    else:
                        assert '(INJECTED)' in hit
                        refuse(result)
                    after = state(store)
                    observation = invoke(store, 'verify', tag+'-observed')
                    if object_path(store, expected).exists():
                        good(observation)  # complete object may precede acknowledgement
                    else:
                        refuse(observation)
                    recovery = recover(store, tag)
                    record({'id': tag, **spec, 'hit': hit, 'fault_returncode': result['returncode'],
                            'injection': injection, 'state_after_fault': after,
                            'observed_after_fault': observation['outcome'], 'recovery_ms': recovery,
                            'unreferenced_incoming_after_recovery': [p for p in state(store) if p.startswith('incoming/')]})

            for damage in ('bitflip', 'truncate', 'missing'):
                tag = 'map-'+damage
                with tempfile.TemporaryDirectory(prefix='nia-map-chaos-damage-') as temp:
                    store = copy_base(temp)
                    good(invoke(store, 'prepare', tag+'-prepare'))
                    p = object_path(store, expected)
                    raw = p.read_bytes()
                    offset = rng.randrange(len(raw))
                    if damage == 'missing':
                        p.unlink()
                    else:
                        p.chmod(0o600)
                        p.write_bytes(raw[:offset]+bytes([raw[offset] ^ 1])+raw[offset+1:] if damage == 'bitflip' else raw[:offset])
                        p.chmod(0o400)
                    changed = state(store)
                    refuse(invoke(store, 'verify', tag+'-damaged'))
                    refuse(invoke(store, 'retention', tag+'-retention'))
                    assert state(store) == changed
                    if damage != 'missing':
                        refuse(invoke(store, 'prepare', tag+'-damaged-prepare'))
                        p.unlink()  # explicit lab quarantine
                    record({'id': tag, 'kind': 'map-corruption', 'damage': damage, 'offset': offset,
                            'explicit_lab_quarantine': damage != 'missing', 'recovery_ms': recover(store, tag)})

            required = {name: hashes[name] for name in ('receipt', 'policy', 'original.deb', 'control', 'InRelease', 'Packages', 'keyring')}
            required.update(catalog=catalog, closure=closure)
            for name, address in required.items():
                tag = 'lost-'+name
                with tempfile.TemporaryDirectory(prefix='nia-map-chaos-loss-') as temp:
                    store = copy_base(temp)
                    good(invoke(store, 'prepare', tag+'-prepare'))
                    p, held = object_path(store, address), store/'held-original'
                    p.rename(held)
                    refuse(invoke(store, 'verify', tag+'-damaged'))
                    refuse(invoke(store, 'retention', tag+'-retention'))
                    refuse(invoke(store, 'prepare', tag+'-damaged-prepare'))
                    assert not p.exists(), 'missing required object reconstructed'
                    held.rename(p)
                    record({'id': tag, 'kind': 'required-reference-loss', 'object': name, 'sha256': address,
                            'explicit_lab_restore': True, 'recovery_ms': recover(store, tag)})

            for name in ('store.lock', 'objects', 'incoming', 'pins'):
                tag = 'structure-'+name
                with tempfile.TemporaryDirectory(prefix='nia-map-chaos-structure-') as temp:
                    store = copy_base(temp)
                    p, held = store/name, store/('held-'+name)
                    p.rename(held)
                    refuse(invoke(store, 'prepare', tag+'-damaged'))
                    assert not p.exists()
                    held.rename(p)
                    record({'id': tag, 'kind': 'structure-loss', 'object': name,
                            'explicit_lab_restore': True, 'recovery_ms': recover(store, tag)})

            read_points = [(i+1, line) for i, line in enumerate(calls(read['trace'], 'pread64')) if expected[2:] in line]
            assert len(read_points) >= 2
            delays = [('verify', 'pread64', *read_points[0]), ('verify', 'pread64', *read_points[-1])]
            final_sync = [spec for spec in schedule if spec['syscall'] == 'fsync' and spec['kind'] == 'io-error']
            delays += [('prepare', 'fsync', spec['nth'], spec['baseline']) for spec in sorted(final_sync, key=lambda s:s['nth'])[-2:]]
            for i, (action, syscall, nth, original_line) in enumerate(delays):
                tag = 'delay-%02d' % i
                with tempfile.TemporaryDirectory(prefix='nia-map-chaos-delay-') as temp:
                    store = copy_base(temp)
                    if action == 'verify':
                        good(invoke(store, 'prepare', tag+'-prepare'))
                    result = invoke(store, action, tag+'-fault', injection=f'{syscall}:delay_enter=1500ms:when={nth}', deadline=1000)
                    hit_calls = calls(result['trace'], syscall)
                    assert len(hit_calls) >= nth and '(DELAYED)' in hit_calls[nth-1] and str(store) in hit_calls[nth-1], result
                    refuse(result)
                    assert result['outcome'] == 'STALE'
                    record({'id': tag, 'kind': 'deadline-delay', 'action': action, 'syscall': syscall, 'nth': nth,
                            'baseline': original_line, 'hit': hit_calls[nth-1], 'deadline_ms': 1000, 'injected_delay_ms': 1500,
                            'map_present_after_failure': object_path(store, expected).exists(), 'elapsed_ms': result['ms'],
                            'recovery_ms': recover(store, tag)})

            rename = next(spec for spec in schedule if spec['syscall'] == 'renameat2' and spec['kind'] == 'kill')
            for i in range(2):
                tag = 'kill-corrupt-%d' % i
                with tempfile.TemporaryDirectory(prefix='nia-map-chaos-combined-') as temp:
                    store = copy_base(temp)
                    result = invoke(store, 'prepare', tag+'-kill', injection=f"renameat2:signal=SIGKILL:when={rename['nth']}")
                    assert result['returncode'] == -signal.SIGKILL and 'killed by SIGKILL' in result['trace']
                    hit = calls(result['trace'], 'renameat2')[rename['nth']-1]
                    assert expected[2:] in hit and str(store) in hit
                    name = rng.choice(('original.deb', 'control', 'receipt'))
                    p = object_path(store, hashes[name])
                    raw = p.read_bytes()
                    offset = rng.randrange(len(raw))
                    p.chmod(0o600)
                    p.write_bytes(raw[:offset]+bytes([raw[offset] ^ 1])+raw[offset+1:])
                    p.chmod(0o400)
                    refuse(invoke(store, 'verify', tag+'-damaged'))
                    refuse(invoke(store, 'prepare', tag+'-damaged-prepare'))
                    p.chmod(0o600)
                    p.write_bytes(raw)  # explicit restoration of this injected fault only
                    p.chmod(0o400)
                    record({'id': tag, 'kind': 'kill-then-corrupt', 'object': name, 'offset': offset,
                            'hit': hit, 'nth': rename['nth'], 'explicit_lab_restore': True,
                            'recovery_ms': recover(store, tag)})

            assert {name: sha((media/name).read_bytes()) for name in artifacts} == hashes
            durations = sorted(row['recovery_ms'] for row in report['cases'])
            counts = dict(Counter(row['kind'] for row in report['cases']))
            assert len(durations) == len(schedule)+22, counts
            report.update(result='pass', completed_utc=time.time(), case_count=len(durations), counts=counts,
                          observed_false_successes=0, untriggered_faults_counted=0, public_inputs_unchanged=True,
                          recovery_ms={'p50': durations[(len(durations)-1)//2],
                                       'p95': durations[int((len(durations)-1)*.95)], 'max': max(durations)})
            persist()
            print(json.dumps({k: report[k] for k in ('result', 'seed', 'case_count', 'counts', 'recovery_ms')}, indent=2))
        except BaseException as exc:
            report.update(result='failed', failure=repr(exc))
            persist()
            raise


if __name__ == '__main__':
    main()
