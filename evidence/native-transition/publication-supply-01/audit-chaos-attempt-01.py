# SPDX-License-Identifier: MIT
"""Independent readback of public checkpoint, WAL chains and actual fault traces."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

work=Path(__file__).resolve().parent

def sha(raw): return hashlib.sha256(raw).digest()
def u64(raw,offset): return struct.unpack_from('>Q',raw,offset)[0]
def state(raw):
    assert len(raw)==192 and raw[:8]==b'MCROOT02' and raw[160:]==sha(raw[:160]) and raw[144:160]==bytes(16)
    assert raw[8:24]==bytes([31])*16
    return dict(generation=u64(raw,24),active=raw[32:48],plan=raw[48:80],accepted=raw[80:112],catalog=raw[112:144])
def journal(raw,transaction,plan,receipt):
    assert len(raw)%256==0 and len(raw)>=4*256
    previous=bytes(32); kinds=[]
    for i in range(len(raw)//256):
        entry=raw[i*256:(i+1)*256]
        assert entry[:8]==b'MCLOG002' and u64(entry,8)==i+1 and entry[224:]==sha(entry[:224])
        assert entry[18:24]==bytes(6) and entry[152:224]==bytes(72)
        assert entry[24:40]==bytes([31])*16 and entry[40:56]==transaction
        assert u64(entry,56)==1 and u64(entry,64)==2 and u64(entry,80)==1
        assert entry[120:152]==previous; previous=sha(entry)
        kind=struct.unpack_from('>H',entry,16)[0]; kinds.append(kind)
        if kind==1: assert i==0 and entry[88:120]==plan and u64(entry,72)==0
        if kind in (5,6): assert entry[88:120]==receipt and u64(entry,72)==0
    assert kinds[:4]==[1,2,3,4]
    return kinds

counts=Counter();summaries=[]
for directory in sorted((work/'chaos').glob('attempt-*')):
    if not directory.is_dir(): continue
    report=json.loads((directory/'report.json').read_text())
    if report['result']!='pass':
        assert report['result']=='failed'
        continue
    checkpoint=directory/'checkpoint';cas=checkpoint/'store'
    def obj(address):
        if isinstance(address,bytes): address=address.hex()
        p=cas/'objects'/address[:2]/address[2:];assert p.stat().st_size<=1024*1024
        raw=p.read_bytes();assert sha(raw).hex()==address;return raw
    expected=bytes.fromhex(report['expected_plan']); manifest=obj(report['manifest']);policy=obj(report['policy']);mapping=obj(report['supply_map'])
    assert manifest[:8]==b'NIAGEN04' and len(manifest)==288 and manifest[192:224].hex()==report['policy']
    assert policy[:8]==b'NIASPOL1' and len(policy)==136 and u64(policy,40)==1000 and u64(policy,48)==1
    key=Ed25519PrivateKey.from_private_bytes(bytes([1])*32).public_key()
    assert policy[56:88]==bytes([71])*32 and policy[88:120]==key.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    assert u64(policy,120)==7 and u64(policy,128)==600 and policy[8:40].hex()==report['supply_map']
    assert len(mapping)==256 and mapping[:8]==b'NIASMAP1' and mapping[8:24]==bytes([31])*16 and mapping[24:88]==bytes(64)
    assert mapping[88:120]==manifest[56:88] and mapping[120:152]==manifest[128:160] and u64(mapping,152)==1
    supply=obj(report['supply_receipt']);assert mapping[224:256]==sha(supply) and len(supply)==320 and supply[:8]==b'NIASUP01'
    assert supply[8:40]==policy[56:88] and supply[72:136]==mapping[160:224]
    assert (u64(supply,232),u64(supply,240),u64(supply,248))==(7,1000,1600)
    domain=b'NiaOS/archive-supply/v1';key.verify(supply[256:],struct.pack('>H',len(domain))+domain+supply[:256])
    for at in range(40,232,32):obj(supply[at:at+32])
    actual=obj(mapping[160:192]);fixture=(work/'workspace/pkgcore/tests/fixtures/selected-catalog/empty.deb').read_bytes();assert actual==fixture
    initial=state((checkpoint/'state/root.state').read_bytes());transaction=initial['active']
    assert initial['generation']==0 and initial['accepted']==initial['catalog']==bytes(32) and initial['plan']==expected
    plan=obj(expected);assert plan[:8]==b'MCPLAN02' and plan[8:24]==bytes([31])*16 and plan[24:40]==transaction
    assert plan[72:104]==manifest[56:88] and (cas/'pins'/transaction.hex()).read_bytes()==expected
    descriptor=(checkpoint/'root/generation.next').read_bytes();assert descriptor[:8]==b'NIAPUB01' and descriptor[160:]==sha(descriptor[:160])
    offset=196+struct.unpack_from('>I',plan,192)[0];assert plan[offset+168:offset+200]==sha(descriptor)
    assert descriptor[40:72]==sha(manifest) and descriptor[72:104]==manifest[56:88] and u64(descriptor,104)==1
    health=manifest[256:288]
    assert journal((checkpoint/'state'/('tx-'+transaction.hex()+'.log')).read_bytes(),transaction,expected,health)==[1,2,3,4]
    actual_inventory={str(p.relative_to(checkpoint)) for p in checkpoint.rglob('*') if p.is_file()}
    assert actual_inventory==set(report['checkpoint_inventory'])
    for name,row in report['checkpoint_inventory'].items():
        raw=(checkpoint/name).read_bytes();assert sha(raw).hex()==row['sha256'] and len(raw)==row['size']
    assert len(report['cases'])==report['case_count'] and len({row['id'] for row in report['cases']})==report['case_count']
    local=Counter(row['kind'] for row in report['cases']);assert dict(local)==report['counts']
    for row in report['cases']:
        assert row['result']=='pass' and row['recovery_ms']>0
        tag=row['id']
        recovered=state((directory/(tag+'-recovered.root-state')).read_bytes())
        assert recovered==dict(generation=1,active=bytes(16),plan=bytes(32),accepted=expected,catalog=manifest[56:88])
        kinds=journal((directory/(tag+'-recovered.journal')).read_bytes(),transaction,expected,health)
        assert kinds[-1]==6 and all(k in (5,6) for k in kinds[4:])
        for suffix in ('-resume.log','-replayed.log'):
            log=(directory/(tag+suffix)).read_text()
            assert re.search(r'^LAB_RESULT OK '+expected.hex()+r'$',log,re.M) and 'FAIL:' not in log
        if row['kind'] in ('io-error','kill','deadline-delay','kill-then-loss'):
            suffix='-kill.trace' if row['kind']=='kill-then-loss' else '-fault.trace'
            trace=(directory/(tag+suffix)).read_text();assert row['hit'] in trace.splitlines()
            if row['kind'] in ('kill','kill-then-loss'):assert 'killed by SIGKILL' in trace
            if row['kind']=='io-error':assert '(INJECTED)' in row['hit'] and ('EIO' in row['hit'] or 'ENOSPC' in row['hit'])
            if row['kind']=='deadline-delay':
                assert '(DELAYED)' in row['hit'] and row['injected_delay_ms']>row['deadline_ms']
                assert 'LAB_RESULT STALE '+expected.hex() in (directory/(tag+'-fault.log')).read_text()
        if row['kind'] in ('required-reference-loss','structure-loss','retained-corruption','kill-then-loss'):
            assert 'LAB_RESULT OK ' not in (directory/(tag+'-damaged.log')).read_text()
        if 'state_after_fault' in row:
            raw=(directory/(tag+'-fault-state.root-state')).read_bytes()
            observed=state(raw);assert observed['generation']==row['state_after_fault']['generation'] and sha(raw).hex()==row['state_after_fault']['root_state_sha256']
            journal((directory/(tag+'-fault-state.journal')).read_bytes(),transaction,expected,health)
    counts.update(local);summaries.append(dict(path=directory.name,seed=report['seed'],case_count=report['case_count'],report_sha256=sha((directory/'report.json').read_bytes()).hex()))
assert len(summaries)==2
result=dict(result='pass',campaigns=summaries,counts=dict(counts),case_count=sum(counts.values()),
            scope='independent pinned plans, v4 manifest/policy/map/signature, observed root.state and WAL chains, actual injection traces and recorded recovery')
(work/'chaos/audit.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS independent publication chaos readback',result['case_count'])
