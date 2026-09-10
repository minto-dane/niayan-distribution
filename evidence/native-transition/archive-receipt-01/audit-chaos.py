# SPDX-License-Identifier: MIT
"""Independent readback of completed campaign artifacts; no fault injection."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

work = Path(__file__).resolve().parent
totals = Counter()
records = []
for name in ('attempt-04', 'attempt-05'):
    directory = work/'chaos'/name
    report = json.loads((directory/'report.json').read_text())
    assert report['result'] == 'pass'
    media = directory/'public-fixture'
    artifacts = {p.name: p.read_bytes() for p in media.iterdir()}
    hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in artifacts.items()}
    assert {name: {'sha256': hashes[name], 'size': len(raw)} for name, raw in artifacts.items()} == report['public_inputs']
    wire = artifacts['receipt']
    assert len(wire) == 320 and wire[:8] == b'NIASUP01' and wire[8:40] == artifacts['scope']
    domain = b'NiaOS/archive-supply/v1'
    Ed25519PublicKey.from_public_bytes(artifacts['public-key']).verify(wire[256:], struct.pack('>H', len(domain))+domain+wire[:256])
    names = ('policy', 'original.deb', 'control', 'InRelease', 'Packages', 'keyring')
    for i, original in enumerate(names):
        assert wire[40+32*i:72+32*i].hex() == hashes[original]
    epoch, checked, expires = struct.unpack('>QQQ', wire[232:256])
    assert epoch == 7 and checked < expires and expires-checked <= 1800
    assert report['completed_utc'] < expires
    assert len(report['cases']) == report['case_count'] == 92
    assert len({row['id'] for row in report['cases']}) == 92
    counts = Counter(row['kind'] for row in report['cases'])
    assert dict(counts) == report['counts']
    for row in report['cases']:
        tag = row['id']
        assert row['result'] == 'pass' and row['recovery_ms'] > 0
        recovered = (directory/(tag+'-recovered.log')).read_text()
        assert ('RESULT OK '+hashes['receipt']) in recovered.splitlines()
        assert 'VIOLATION' not in recovered and 'FAIL ' not in recovered
        resume = (directory/(tag+'-resume.log')).read_text()
        acks = re.findall(r'^ACK (\S+) ([0-9a-f]{64})$', resume, re.M)
        assert len(acks) == 7 and dict(acks) == {n: hashes[n] for n in names+('receipt',)}
        if row['kind'] in ('kill', 'io-error', 'deadline-delay', 'kill-then-corrupt'):
            suffix = '-kill.trace' if row['kind'] == 'kill-then-corrupt' else '-fault.trace'
            trace = (directory/(tag+suffix)).read_text()
            assert row['hit'] in trace.splitlines()
            if row['kind'] in ('kill', 'kill-then-corrupt'):
                assert 'killed by SIGKILL' in trace
            elif row['kind'] == 'io-error':
                assert '(INJECTED)' in row['hit'] and row['error'] in row['hit']
            else:
                assert '(DELAYED)' in row['hit'] and row['injected_delay_ms'] > row['deadline_ms']
                assert row['outcome_after_fault'] == 'STALE'
        if row['kind'] in ('corruption', 'kill-then-corrupt'):
            assert 'RESULT OK' not in (directory/(tag+'-damaged.log')).read_text()
        if row['kind'] == 'stop-lock-resume':
            assert row['pidfd'] and row['observed_stop_signal'] == 19
            assert ('RESULT STALE '+'0'*64) in (directory/(tag+'.log')).read_text()
    totals.update(counts)
    records.append({'campaign': name, 'cases': 92, 'seed': report['seed'],
                    'report_sha256': hashlib.sha256((directory/'report.json').read_bytes()).hexdigest()})
assert sum(totals.values()) == 184
output = {'result': 'pass', 'campaigns': records, 'counts': dict(totals),
          'case_count': 184, 'scope': 'public signatures, original hashes, real fault traces and successful recovery logs'}
(work/'chaos/audit.json').write_text(json.dumps(output, indent=2)+'\n')
print('PASS independent readback: 184 real fault observations and original-bound recoveries')
