# SPDX-License-Identifier: MIT
"""Bounded destructive CAS qualification. Only freshly owned temporary trees.

Run as an unprivileged user in the pinned, network-disabled development image.
All faults target a direct child or its private temporary CAS. Never accepts a
host store path. strace injects errors/signals, never fabricated success.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import selectors
import signal
import subprocess
import tempfile
import time

import test_archive_receipt as fixtures
from archive_receipt import scope
from deb_archive import ar_members, decompress, tar_inventory, MAX_CONTROL

HERE = Path(__file__).resolve().parent
DRIVER = HERE/'bin/chaos_driver'
TRACE = HERE/'strace'
ZERO = '0'*64
SYSCALLS = ('write', 'fsync', 'renameat2', 'pread64')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20260910)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise SystemExit('unprivileged isolated lab required')
    out = args.output.resolve()
    out.mkdir(mode=0o700)  # refuse overwrite of previous attempts
    rng = random.Random(args.seed)
    report = {'schema': 'org.niaos.cas-chaos/v1', 'seed': args.seed, 'result': 'running',
              'uid': os.geteuid(), 'started_utc': time.time(), 'cases': [],
              'driver_sha256': sha(DRIVER.read_bytes()), 'strace_sha256': sha(TRACE.read_bytes()),
              'limits': {'memory_bytes': 3221225472, 'swap_bytes': 0, 'cpu_cores': 1, 'pids': 128},
              'scope': 'per-original authenticated receipt, real native CAS import/reopen/verification',
              'physical_power_loss': False, 'boot_or_generation_transaction_qualification': False}
    media = out/'public-fixture'
    media.mkdir(mode=0o700)
    fixtures.ReceiptTests.setUpClass()
    case = fixtures.ReceiptTests()
    try:
        case.setUp()
        with case.remote.client(case.cache) as repository:
            receipt = case.issue(repository, maximum_lifetime_seconds=1800)
            expected_scope = bytes.fromhex(scope(repository, case.target))
        original = case.fixture.fixture.deb
        control = tar_inventory(decompress(*ar_members(original)[1], MAX_CONTROL), control=True)[1]['control']
        artifacts = {'receipt': receipt.wire, 'policy': receipt.policy_bytes, 'original.deb': original,
                     'control': control, 'InRelease': case.fixture.signed, 'Packages': case.fixture.fixture.packed,
                     'keyring': case.fixture.fixture.keyring, 'public-key': case.public_key, 'scope': expected_scope}
        for name, raw in artifacts.items():
            (media/name).write_bytes(raw)
            (media/name).chmod(0o400)
    finally:
        case.doCleanups()
        fixtures.ReceiptTests.tearDownClass()
    hashes = {name: sha(raw) for name, raw in artifacts.items()}
    report['public_inputs'] = {name: {'sha256': hashes[name], 'size': len(raw)} for name, raw in artifacts.items()}
    objects = [name for name in artifacts if name not in ('scope', 'public-key')]

    def persist():
        (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')

    def object_path(store, name):
        h = hashes[name]
        return store/'objects'/h[:2]/h[2:]

    def state(store):
        # Bounded fixture, no external path input or recursive shared-work walk.
        result = {'objects': {}, 'incoming': {}, 'missing': []}
        for section in ('objects', 'incoming'):
            for p in sorted((store/section).rglob('*')):
                if p.is_file():
                    assert not p.is_symlink() and p.stat().st_size < 16*1024*1024
                    result[section][str(p.relative_to(store))] = {'sha256': sha(p.read_bytes()), 'size': p.stat().st_size}
        result['missing'] = [name for name in objects if not object_path(store, name).exists()]
        return result

    def invoke(store, action, tag, inject=None, deadline=30000, trace=False):
        command = [str(DRIVER), action, str(store), str(media), str(deadline)]
        tracepath = out/(tag+'.trace')
        if trace or inject:
            command = [str(TRACE), '-qq', '-yy', '-s', '80', '-e', 'trace='+','.join(SYSCALLS),
                       '-o', str(tracepath), *(['-e', 'inject='+inject] if inject else []), *command]
        start = time.monotonic()
        p = subprocess.run(command, text=True, capture_output=True, timeout=40,
                           env={**os.environ, 'LD_LIBRARY_PATH': str(HERE/'lib')})
        elapsed = (time.monotonic()-start)*1000
        raw = p.stdout+p.stderr
        (out/(tag+'.log')).write_text(raw)
        assert 'VIOLATION' not in raw, raw
        for line in p.stdout.splitlines():
            if line.startswith('ACK '):
                _, name, h = line.split()
                assert h == hashes[name]
                assert sha(object_path(store, name).read_bytes()) == h, 'acknowledged object damaged'
        result = re.search(r'^RESULT\s+(\w+) ([0-9a-f]{64})$', p.stdout, re.M)
        if result:
            assert result[2] == (hashes['receipt'] if result[1] == 'OK' else ZERO)
        return {'returncode': p.returncode, 'ms': elapsed, 'stdout': p.stdout, 'stderr': p.stderr,
                'outcome': result[1] if result else None,
                'trace': tracepath.read_text() if tracepath.exists() else '', 'command': command}

    def good(result):
        assert result['returncode'] == 0 and result['outcome'] == 'OK', result

    def refused(result):
        assert result['returncode'] in (10, 11), result
        assert result['outcome'] not in ('OK',) and (result['outcome'] or 'FAIL ' in result['stdout']), result

    def init(store, tag, populated=False):
        assert invoke(store, 'init', tag+'-init')['returncode'] == 0
        if populated:
            assert invoke(store, 'import', tag+'-import')['returncode'] == 0
            good(invoke(store, 'verify', tag+'-initial-verify'))

    def recover(store, tag):
        start = time.monotonic()
        assert invoke(store, 'import', tag+'-resume')['returncode'] == 0
        good(invoke(store, 'verify', tag+'-recovered'))
        return (time.monotonic()-start)*1000

    def record(row):
        row['result'] = 'pass'
        report['cases'].append(row)
        persist()
        print('PASS', row['id'], row['kind'], flush=True)

    def candidates(raw, call, section):
        occurrences = [line for line in raw.splitlines() if line.startswith(call+'(')]
        return [(i+1, line) for i, line in enumerate(occurrences) if '/'+section+'/' in line or '/'+section+'>' in line]

    def chosen(values, limit):
        assert values
        if len(values) <= limit:
            return values
        return [values[0], *rng.sample(values[1:-1], limit-2), values[-1]]

    persist()
    try:
        with tempfile.TemporaryDirectory(prefix='nia-chaos-baseline-') as temp:
            store = Path(temp)
            init(store, 'baseline')
            baseline = invoke(store, 'import', 'baseline-import', trace=True)
            assert baseline['returncode'] == 0, baseline
            good(invoke(store, 'verify', 'baseline-prime'))
            reads = invoke(store, 'verify', 'baseline-read', trace=True)
            good(reads)
        schedule = []
        for syscall, error, section in (('write', 'ENOSPC', 'incoming'), ('fsync', 'EIO', 'objects'),
                                         ('renameat2', 'EIO', 'incoming')):
            possible = candidates(baseline['trace'], syscall, section)
            if syscall == 'fsync':
                possible = sorted(set(possible+candidates(baseline['trace'], syscall, 'incoming')))
            for nth, line in chosen(possible, 12):
                schedule.extend([{'kind': 'io-error', 'syscall': syscall, 'nth': nth, 'error': error, 'baseline': line},
                                 {'kind': 'kill', 'syscall': syscall, 'nth': nth, 'baseline': line}])
        rng.shuffle(schedule)
        report['schedule'] = schedule
        persist()
        for i, spec in enumerate(schedule):
            tag = 'fault-%03d' % i
            with tempfile.TemporaryDirectory(prefix='nia-chaos-fault-') as temp:
                store = Path(temp)
                init(store, tag)
                effect = 'signal=SIGKILL' if spec['kind'] == 'kill' else 'error='+spec['error']
                injection = f"{spec['syscall']}:{effect}:when={spec['nth']}"
                result = invoke(store, 'import', tag+'-fault', inject=injection)
                calls = [line for line in result['trace'].splitlines() if line.startswith(spec['syscall']+'(')]
                assert len(calls) >= spec['nth'], 'injection never reached'
                hit = calls[spec['nth']-1]
                assert str(store) in hit and ('/incoming' in hit or '/objects' in hit), hit
                if spec['kind'] == 'kill':
                    assert result['returncode'] == -signal.SIGKILL and 'killed by SIGKILL' in result['trace'], result
                else:
                    assert '(INJECTED)' in hit and spec['error'] in hit, hit
                    refused(result)
                before = state(store)
                observation = invoke(store, 'verify', tag+'-after-fault')
                if before['missing']:
                    refused(observation)
                elif observation['outcome'] == 'OK':
                    good(observation)  # complete publication may precede last ACK
                else:
                    refused(observation)
                recovery_ms = recover(store, tag)
                record({'id': tag, **spec, 'injection': injection, 'hit': hit, 'fault_returncode': result['returncode'],
                        'acknowledged': [line for line in result['stdout'].splitlines() if line.startswith('ACK ')],
                        'state_after_fault': before, 'outcome_after_fault': observation['outcome'],
                        'recovery_ms': recovery_ms, 'incoming_after_recovery': state(store)['incoming']})

        # Stack two faults: kill after at least one durable ACK, then damage an
        # acknowledged object before recovery. Each mutation is in a fresh lab.
        for i, spec in enumerate(rng.sample([s for s in schedule if s['kind'] == 'kill' and s['syscall'] == 'renameat2' and s['nth'] > 1], 4)):
            tag = 'kill-corrupt-%d' % i
            with tempfile.TemporaryDirectory(prefix='nia-chaos-combined-') as temp:
                store = Path(temp)
                init(store, tag)
                result = invoke(store, 'import', tag+'-kill', inject=f"renameat2:signal=SIGKILL:when={spec['nth']}")
                assert result['returncode'] == -signal.SIGKILL and 'killed by SIGKILL' in result['trace']
                calls = [line for line in result['trace'].splitlines() if line.startswith('renameat2(')]
                assert len(calls) == spec['nth'] and str(store) in calls[-1]
                acks = [line.split()[1] for line in result['stdout'].splitlines() if line.startswith('ACK ')]
                assert acks
                name = rng.choice(acks)
                p = object_path(store, name)
                raw = p.read_bytes()
                offset = rng.randrange(len(raw))
                p.chmod(0o600)
                p.write_bytes(raw[:offset]+bytes([raw[offset] ^ 1])+raw[offset+1:])
                p.chmod(0o400)
                damaged = state(store)
                refused(invoke(store, 'verify', tag+'-damaged'))
                refused(invoke(store, 'import', tag+'-resume-damaged'))
                p.unlink()  # explicit lab quarantine of known injected corruption
                recovery_ms = recover(store, tag)
                record({'id': tag, 'kind': 'kill-then-corrupt', 'nth': spec['nth'], 'hit': calls[-1],
                        'object': name, 'offset': offset, 'state_after_fault': damaged,
                        'explicit_lab_quarantine': True, 'recovery_ms': recovery_ms})

        for name in objects:
            for damage in ('bitflip', 'truncate', 'missing'):
                tag = 'damage-'+name+'-'+damage
                with tempfile.TemporaryDirectory(prefix='nia-chaos-damage-') as temp:
                    store = Path(temp)
                    init(store, tag, populated=True)
                    p = object_path(store, name)
                    raw = p.read_bytes()
                    offset = rng.randrange(len(raw))
                    if damage == 'missing':
                        p.unlink()
                    else:
                        p.chmod(0o600)
                        changed = (raw[:offset]+bytes([raw[offset] ^ (1 << rng.randrange(8))])+raw[offset+1:]) if damage == 'bitflip' else raw[:offset]
                        p.write_bytes(changed)
                        p.chmod(0o400)
                    damaged = state(store)
                    observation = invoke(store, 'verify', tag+'-damaged')
                    refused(observation)
                    assert state(store) == damaged, 'verification modified damaged required objects'
                    if damage != 'missing':
                        # Reimport must not silently overwrite a corrupted immutable address.
                        refused(invoke(store, 'import', tag+'-reimport-damaged'))
                        p.unlink()  # explicit lab quarantine, never an automatic product repair
                    recovery_ms = recover(store, tag)
                    record({'id': tag, 'kind': 'corruption', 'object': name, 'damage': damage, 'offset': offset,
                            'outcome_after_fault': observation['outcome'], 'state_after_fault': damaged,
                            'explicit_lab_quarantine': damage != 'missing', 'recovery_ms': recovery_ms})

        for missing in ('store.lock', 'objects', 'incoming', 'pins'):
            tag = 'missing-structure-'+missing.replace('.', '-')
            with tempfile.TemporaryDirectory(prefix='nia-chaos-structure-') as temp:
                store = Path(temp)
                init(store, tag, populated=True)
                p = store/missing
                held = store/('held-'+missing)
                p.rename(held)
                refused(invoke(store, 'verify', tag+'-damaged'))
                assert not p.exists(), 'missing store structure recreated'
                refused(invoke(store, 'init', tag+'-reinitialize'))
                assert not p.exists(), 'bootstrap repaired nonempty damaged store'
                held.rename(p)  # restore retained original structure, not reinitialize
                recovery_ms = recover(store, tag)
                record({'id': tag, 'kind': 'structural-loss', 'missing': missing, 'recovery_ms': recovery_ms,
                        'explicit_lab_restore': True})

        for nth, line in chosen(candidates(reads['trace'], 'pread64', 'objects'), 8):
            tag = 'delay-%03d' % nth
            with tempfile.TemporaryDirectory(prefix='nia-chaos-delay-') as temp:
                store = Path(temp)
                init(store, tag, populated=True)
                # Permit measured tracer overhead, but inject a delay greater
                # than the entire finite request budget. Require the actual hit.
                result = invoke(store, 'verify', tag+'-fault', inject=f'pread64:delay_enter=600ms:when={nth}', deadline=200)
                calls = [line for line in result['trace'].splitlines() if line.startswith('pread64(')]
                assert len(calls) >= nth and '(DELAYED)' in calls[nth-1] and str(store) in calls[nth-1], result
                refused(result)
                assert result['outcome'] == 'STALE', result
                recovery_ms = recover(store, tag)
                record({'id': tag, 'kind': 'deadline-delay', 'nth': nth, 'baseline': line,
                        'hit': calls[nth-1], 'outcome_after_fault': result['outcome'], 'elapsed_ms': result['ms'],
                        'deadline_ms': 200, 'injected_delay_ms': 600,
                        'recovery_ms': recovery_ms})

        for i in range(3):
            tag = 'stop-resume-%d' % i
            with tempfile.TemporaryDirectory(prefix='nia-chaos-stop-') as temp:
                store = Path(temp)
                init(store, tag, populated=True)
                command = [str(DRIVER), 'verify-wait', str(store), str(media), '50']
                child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                fd = os.pidfd_open(child.pid)
                try:
                    with selectors.DefaultSelector() as selector:
                        selector.register(child.stdout, selectors.EVENT_READ)
                        assert selector.select(5), 'missing readiness acknowledgement'
                    assert child.stdout.readline() == 'READY\n'
                    signal.pidfd_send_signal(fd, signal.SIGSTOP)
                    event = os.waitid(os.P_PIDFD, fd, os.WSTOPPED)
                    assert event.si_code == os.CLD_STOPPED and event.si_status == signal.SIGSTOP
                    stopped = time.monotonic()
                    # A competing native opener must refuse the live writer's lock.
                    contender = invoke(store, 'verify', tag+'-contender')
                    refused(contender)
                    pause = rng.uniform(.08, .16)
                    time.sleep(pause)
                    signal.pidfd_send_signal(fd, signal.SIGCONT)
                    stdout, stderr = child.communicate('continue\n', timeout=5)
                    (out/(tag+'.log')).write_text('READY\n'+stdout+stderr)
                    assert child.returncode == 10 and 'RESULT STALE '+ZERO in stdout
                    resumed_ms = (time.monotonic()-stopped)*1000
                finally:
                    if child.poll() is None:
                        signal.pidfd_send_signal(fd, signal.SIGKILL)
                        child.wait(timeout=5)
                    os.close(fd)
                recovery_ms = recover(store, tag)
                record({'id': tag, 'kind': 'stop-lock-resume', 'child_pid': child.pid, 'pidfd': True,
                        'observed_stop_signal': event.si_status, 'pause_seconds': pause,
                        'stop_to_refusal_ms': resumed_ms, 'recovery_ms': recovery_ms})

        assert {name: sha((media/name).read_bytes()) for name in artifacts} == hashes
        durations = sorted(row['recovery_ms'] for row in report['cases'])
        kinds = sorted({row['kind'] for row in report['cases']})
        report.update(result='pass', completed_utc=time.time(), case_count=len(durations),
                      counts={kind: sum(row['kind'] == kind for row in report['cases']) for kind in kinds},
                      observed_false_successes=0, untriggered_faults_counted=0,
                      recovery_ms={'p50': durations[(len(durations)-1)//2],
                                   'p95': durations[int((len(durations)-1)*.95)], 'max': max(durations)},
                      public_inputs_unchanged=True)
        persist()
        print(json.dumps({key: report[key] for key in ('result', 'seed', 'case_count', 'counts', 'recovery_ms')}, indent=2))
    except BaseException as exc:
        report['result'] = 'failed'
        report['failure'] = repr(exc)
        persist()
        raise


if __name__ == '__main__':
    main()
