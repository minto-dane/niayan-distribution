# SPDX-License-Identifier: MIT
"""Independent readback of signatures, canonical maps and fault/recovery logs."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

work=Path(__file__).resolve().parent
totals=Counter();campaigns=[]
for directory in sorted((work/'chaos').glob('attempt-*')):
    if not directory.is_dir():continue
    report=json.loads((directory/'report.json').read_text())
    if report['result']!='pass':continue
    media=directory/'public-fixture'
    artifacts={p.name:p.read_bytes() for p in media.iterdir()}
    hashes={name:hashlib.sha256(raw).hexdigest() for name,raw in artifacts.items()}
    assert {name:{'sha256':hashes[name],'size':len(raw)} for name,raw in artifacts.items()}==report['public_inputs']
    receipt=artifacts['receipt'];wire=artifacts['map']
    assert len(receipt)==320 and receipt[:8]==b'NIASUP01' and receipt[8:40]==artifacts['scope']
    domain=b'NiaOS/archive-supply/v1'
    Ed25519PublicKey.from_public_bytes(artifacts['public-key']).verify(receipt[256:],struct.pack('>H',len(domain))+domain+receipt[:256])
    names=('policy','original.deb','control','InRelease','Packages','keyring')
    for i,name in enumerate(names):assert receipt[40+32*i:72+32*i].hex()==hashes[name]
    epoch,checked,expires=struct.unpack('>QQQ',receipt[232:256])
    assert epoch==7 and checked<expires and report['completed_utc']<expires
    assert len(wire)==256 and wire[:24]==b'NIASMAP1'+bytes([104])*16 and wire[24:88]==bytes(64)
    assert struct.unpack('>Q',wire[152:160])==(1,)
    assert wire[160:]==b''.join(hashlib.sha256(artifacts[name]).digest() for name in ('original.deb','control','receipt'))
    assert report['case_count'] in (34,36) and len(report['cases'])==report['case_count']
    assert len({row['id'] for row in report['cases']})==report['case_count']
    counts=Counter(row['kind'] for row in report['cases']);assert dict(counts)==report['counts']
    for row in report['cases']:
        assert row['result']=='pass' and row['recovery_ms']>0
        tag=row['id']
        for suffix in ('-resume.log','-recovered.log'):
            raw=(directory/(tag+suffix)).read_text()
            match=re.search(r'^RESULT OK ([0-9a-f]{64})\s+(\d+)$',raw,re.M)
            assert match and match[1]==hashes['map'] and 0<int(match[2])<=expires
            assert 'VIOLATION' not in raw and 'FAIL ' not in raw
        if row['kind'] in ('io-error','kill','kill-then-corrupt','deadline-delay'):
            suffix='-kill.trace' if row['kind']=='kill-then-corrupt' else '-fault.trace'
            trace=(directory/(tag+suffix)).read_text();assert row['hit'] in trace.splitlines()
            if row['kind'] in ('kill','kill-then-corrupt'):
                assert 'killed by SIGKILL' in trace
            elif row['kind']=='io-error':
                assert '(INJECTED)' in row['hit'] and ('EIO' in row['hit'] or 'ENOSPC' in row['hit'])
            else:
                assert '(DELAYED)' in row['hit'] and row['injected_delay_ms']>row['deadline_ms']
                assert 'RESULT STALE '+'0'*64 in (directory/(tag+'-fault.log')).read_text()
        if row['kind'] in ('map-corruption','required-reference-loss','kill-then-corrupt','structure-loss'):
            raw=(directory/(tag+'-damaged.log')).read_text();assert 'RESULT OK' not in raw
    totals.update(counts)
    campaigns.append({'path':directory.name,'seed':report['seed'],'case_count':report['case_count'],
                      'report_sha256':hashlib.sha256((directory/'report.json').read_bytes()).hexdigest()})
assert len(campaigns)==2
output={'result':'pass','campaigns':campaigns,'counts':dict(totals),'case_count':sum(totals.values()),
        'scope':'independent public signatures/map preimage, actual injected faults, zero failed outputs and original-bound recovery'}
(work/'chaos/audit.json').write_text(json.dumps(output,indent=2)+'\n')
print('PASS independent source map chaos readback:',output['case_count'],'cases')
