# SPDX-License-Identifier: MIT
"""Fault injection into disposable native publication recovery; no host root/boot."""
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
import stat
import struct
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent
DRIVER = Path('/workspace/pkgcore/build/test-bin/run_generation_publication_tests')
MEDIA = Path('/workspace/pkgcore/tests/fixtures/selected-catalog')
TRACE = HERE/'strace'
SYSCALLS = ('write', 'fsync', 'renameat2', 'pread64')


def sha(raw): return hashlib.sha256(raw).hexdigest()
def object_path(store, digest): return store/'objects'/digest[:2]/digest[2:]


def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        assert not path.is_symlink(), path
        if path.is_file():
            assert path.stat().st_size <= 1024*1024, path
            raw = path.read_bytes()
            result[str(path.relative_to(root))] = dict(sha256=sha(raw), size=len(raw), mode=stat.S_IMODE(path.stat().st_mode))
        else:
            assert path.is_dir(), path
    assert sum(row['size'] for row in result.values()) < 16*1024*1024
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert os.geteuid() != 0
    output = args.output.resolve(); output.mkdir(mode=0o700)
    rng = random.Random(args.seed)
    report = dict(result='running', seed=args.seed, cases=[], started_utc=time.time(),
                  driver_sha256=sha(DRIVER.read_bytes()), strace_sha256=sha(TRACE.read_bytes()),
                  scope='native v4 publication root.state and WAL recovery from an actually admitted synthetic stage',
                  supply_observed_at=1000, supply_expires_at=1600, recovery_observation=2000,
                  physical_power_loss=False, real_rootfs_or_boot=False, production_authority=False)

    def persist(): (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    def record(row):
        row['result'] = 'pass'; report['cases'].append(row); persist()
        print('PASS', row['id'], row['kind'], flush=True)
    def calls(raw, syscall): return [line for line in raw.splitlines() if line.startswith(syscall+'(')]

    def invoke(tree, tag, injection=None, deadline=30000, trace=False, checkpoint=False):
        command = [str(DRIVER), *[str(tree/name) for name in ('root','state','store','bank')], str(MEDIA)]
        command += ['checkpoint'] if checkpoint else ['recover', expected, str(deadline)]
        path = output/(tag+'.trace')
        if trace or injection:
            command = [str(TRACE), '-qq', '-yy', '-s', '96', '-e', 'trace='+','.join(SYSCALLS),
                       '-o', str(path), *(['-e','inject='+injection] if injection else []), *command]
        started = time.monotonic()
        value = subprocess.run(command, capture_output=True, text=True, timeout=45,
                               env={**os.environ, 'LD_LIBRARY_PATH':str(HERE/'lib')})
        raw = value.stdout+value.stderr; (output/(tag+'.log')).write_text(raw)
        matched = re.search(r'^LAB_RESULT (\w+) ([0-9a-f]{64})$', raw, re.M)
        if matched: assert matched[2] == expected
        return dict(returncode=value.returncode, outcome=matched[1] if matched else None,
                    stdout=raw, ms=(time.monotonic()-started)*1000,
                    trace=path.read_text() if path.exists() else '', command=command)

    def good(value): assert value['returncode'] == 0 and value['outcome'] == 'OK', value
    def refuse(value):
        assert value['returncode'] == 1 and value['outcome'] != 'OK', value
        assert value['outcome'] is not None or ('FAIL:' in value['stdout'] and 'raised TEST_SUPPORT.FAILURE' in value['stdout']), value
        assert 'raised CONSTRAINT_ERROR' not in value['stdout'] and 'raised STORAGE_ERROR' not in value['stdout'], value

    def check_accepted(tree):
        raw = (tree/'state/root.state').read_bytes()
        assert len(raw) == 192 and raw[:8] == b'MCROOT02' and sha(raw[:160]) == raw[160:].hex()
        assert raw[8:24] == bytes([31])*16 and struct.unpack_from('>Q',raw,24) == (1,)
        assert raw[32:80] == bytes(48) and raw[80:112].hex() == expected and raw[112:144].hex() == catalog
        assert (tree/'root/generation.next').read_bytes() == descriptor
        for name, entry in baseline_objects.items():
            path = tree/name
            assert path.is_file() and sha(path.read_bytes()) == entry['sha256'], name
        return sha(raw)

    def save_state(tree, tag):
        for name, source in [('root-state',tree/'state/root.state'),('journal',tree/'state'/('tx-'+transaction.hex()+'.log'))]:
            assert source.stat().st_size <= 1024*1024
            (output/(tag+'.'+name)).write_bytes(source.read_bytes())

    def recover(tree, tag):
        started = time.monotonic()
        good(invoke(tree, tag+'-resume')); fingerprint = check_accepted(tree)
        good(invoke(tree, tag+'-replayed')); assert check_accepted(tree) == fingerprint
        save_state(tree, tag+'-recovered')
        return (time.monotonic()-started)*1000

    def after_fault(tree, tag):
        save_state(tree, tag+'-fault-state')
        raw = (tree/'state/root.state').read_bytes()
        assert len(raw) == 192 and raw[:8] == b'MCROOT02' and sha(raw[:160]) == raw[160:].hex()
        generation = struct.unpack_from('>Q',raw,24)[0]
        assert generation in (0,1)
        if generation == 0: assert raw[80:144] == bytes(64)
        else: assert raw[80:112].hex() == expected and raw[112:144].hex() == catalog
        assert (raw[32:48] == bytes(16)) == (raw[48:80] == bytes(32))
        if raw[32:48] != bytes(16): assert raw[32:48] == transaction and raw[48:80].hex() == expected
        return dict(generation=generation, active=raw[32:48].hex(), root_state_sha256=sha(raw), inventory=inventory(tree))

    with tempfile.TemporaryDirectory(prefix='nia-publication-base-') as temporary:
        base = Path(temporary)/'base'; base.mkdir(mode=0o700)
        for name in ('root','state','store','bank'): (base/name).mkdir(mode=0o700)
        fixture = invoke(base,'checkpoint',checkpoint=True); assert fixture['returncode'] == 0,fixture
        values = dict(line.split() for line in fixture['stdout'].splitlines() if line.startswith('LAB_'))
        expected = values['LAB_PLAN']; manifest_hash=values['LAB_MANIFEST']; policy_hash=values['LAB_POLICY']
        raw=(base/'state/root.state').read_bytes()
        assert raw[24:32] == bytes(8) and raw[32:48] != bytes(16) and raw[48:80].hex() == expected and raw[80:144] == bytes(64)
        transaction=raw[32:48]
        descriptor=(base/'root/generation.next').read_bytes(); assert descriptor[40:72].hex()==manifest_hash
        manifest=object_path(base/'store',manifest_hash).read_bytes(); assert manifest[:8]==b'NIAGEN04'
        catalog=manifest[56:88].hex(); policy=object_path(base/'store',policy_hash).read_bytes()
        assert policy[:8]==b'NIASPOL1' and struct.unpack_from('>Q',policy,40)==(1000,)
        map_hash=policy[8:40].hex(); mapping=object_path(base/'store',map_hash).read_bytes()
        receipt_hash=mapping[224:256].hex(); receipt=object_path(base/'store',receipt_hash).read_bytes()
        assert struct.unpack_from('>QQ',receipt,240)==(1000,1600)
        original_hash=receipt[72:104].hex(); control_hash=receipt[104:136].hex()
        report.update(expected_plan=expected, manifest=manifest_hash, policy=policy_hash, supply_map=map_hash,
                      supply_receipt=receipt_hash, catalog=catalog, checkpoint_inventory=inventory(base))
        baseline_objects={name:entry for name,entry in inventory(base).items() if name.startswith(('store/objects/','store/pins/','bank/'))}
        shutil.copytree(base,output/'checkpoint')
        def copy_base(parent):
            result=Path(parent)/'case'; shutil.copytree(base,result); return result
        persist()
        try:
            with tempfile.TemporaryDirectory(prefix='nia-publication-baseline-') as temp:
                tree=copy_base(temp); baseline=invoke(tree,'baseline-recovery',trace=True); good(baseline);check_accepted(tree)
            lines=baseline['trace'].splitlines(); points=[]
            for index,line in enumerate(lines):
                if str(tree/'state') not in line: continue
                syscall=line.split('(',1)[0]
                if syscall=='write' and ('/tx-' in line or '"MCROOT02' in line): points.append(index)
                elif syscall=='renameat2' and '"root.state"' in line: points.append(index)
                elif syscall=='fsync': points.append(index)
            assert 8<=len(points)<=24,points
            schedule=[]
            for index in points:
                line=lines[index]; syscall=line.split('(',1)[0]; nth=sum(l.startswith(syscall+'(') for l in lines[:index+1])
                for kind in ('io-error','kill'): schedule.append(dict(kind=kind,syscall=syscall,nth=nth,baseline=line))
            rng.shuffle(schedule);report['schedule']=schedule;persist()
            for i,spec in enumerate(schedule):
                tag='fault-%02d'%i
                with tempfile.TemporaryDirectory(prefix='nia-publication-fault-') as temp:
                    tree=copy_base(temp)
                    effect='signal=SIGKILL' if spec['kind']=='kill' else 'error='+('ENOSPC' if spec['syscall']=='write' else 'EIO')
                    injection=f"{spec['syscall']}:{effect}:when={spec['nth']}"
                    value=invoke(tree,tag+'-fault',injection=injection)
                    reached=calls(value['trace'],spec['syscall']);assert len(reached)>=spec['nth']
                    hit=reached[spec['nth']-1];assert str(tree/'state') in hit,hit
                    if spec['kind']=='kill': assert value['returncode']==-signal.SIGKILL and 'killed by SIGKILL' in value['trace']
                    else: assert '(INJECTED)' in hit;refuse(value)
                    observed=after_fault(tree,tag)
                    record(dict(id=tag,**spec,injection=injection,hit=hit,fault_returncode=value['returncode'],
                                state_after_fault=observed,recovery_ms=recover(tree,tag)))
            required={'policy':policy_hash,'map':map_hash,'receipt':receipt_hash,'original':original_hash,
                      'control':control_hash,'manifest':manifest_hash,'intent':manifest[160:192].hex(),'catalog':catalog}
            for name,address in required.items():
                tag='lost-'+name
                with tempfile.TemporaryDirectory(prefix='nia-publication-loss-') as temp:
                    tree=copy_base(temp);path=object_path(tree/'store',address);held=tree/'withheld';path.rename(held)
                    before=inventory(tree);refuse(invoke(tree,tag+'-damaged'));assert inventory(tree)==before and not path.exists()
                    held.rename(path)
                    record(dict(id=tag,kind='required-reference-loss',sha256=address,explicit_lab_restore=True,recovery_ms=recover(tree,tag)))
            structure=['state/root.state','state/publication.lock','state/root.lock','state/tx-'+transaction.hex()+'.log',
                       'store/store.lock','store/pins/'+transaction.hex(),'bank/'+manifest[8:24].hex()+'/state/generation.lock']
            for i,name in enumerate(structure):
                tag='structure-%d'%i
                with tempfile.TemporaryDirectory(prefix='nia-publication-structure-') as temp:
                    tree=copy_base(temp);path=tree/name;held=tree/'withheld';path.rename(held)
                    before=inventory(tree);refuse(invoke(tree,tag+'-damaged'));assert inventory(tree)==before and not path.exists()
                    held.rename(path)
                    record(dict(id=tag,kind='structure-loss',path=name,explicit_lab_restore=True,recovery_ms=recover(tree,tag)))
            for name in ('state/root.state','state/tx-'+transaction.hex()+'.log','store/objects/'+policy_hash[:2]+'/'+policy_hash[2:]):
                for damage in ('bitflip','truncate'):
                    tag='damage-%d'%len(report['cases'])
                    with tempfile.TemporaryDirectory(prefix='nia-publication-corrupt-') as temp:
                        tree=copy_base(temp);path=tree/name;original=path.read_bytes();mode=stat.S_IMODE(path.stat().st_mode)
                        offset=rng.randrange(len(original));path.chmod(0o600)
                        path.write_bytes(original[:offset]+bytes([original[offset]^1])+original[offset+1:] if damage=='bitflip' else original[:-1]);path.chmod(mode)
                        before=inventory(tree);refuse(invoke(tree,tag+'-damaged'));assert inventory(tree)==before
                        path.chmod(0o600);path.write_bytes(original);path.chmod(mode)
                        record(dict(id=tag,kind='retained-corruption',path=name,damage=damage,offset=offset,explicit_lab_restore=True,recovery_ms=recover(tree,tag)))
            reads=[(i+1,line) for i,line in enumerate(calls(baseline['trace'],'pread64')) if policy_hash[2:] in line]
            syncs=sorted((s for s in schedule if s['kind']=='io-error' and s['syscall']=='fsync'),key=lambda s:s['nth'])
            assert len(reads)>=2 and len(syncs)>=2
            delays=[dict(syscall='pread64',nth=n,baseline=l) for n,l in reads[-2:]]+syncs[-2:]
            for i,spec in enumerate(delays):
                tag='delay-%d'%i
                with tempfile.TemporaryDirectory(prefix='nia-publication-delay-') as temp:
                    tree=copy_base(temp);injection=f"{spec['syscall']}:delay_enter=6000ms:when={spec['nth']}"
                    value=invoke(tree,tag+'-fault',injection=injection,deadline=5000)
                    reached=calls(value['trace'],spec['syscall']);assert len(reached)>=spec['nth']
                    hit=reached[spec['nth']-1];assert '(DELAYED)' in hit and str(tree) in hit;refuse(value)
                    assert value['outcome']=='STALE',value
                    record(dict(id=tag,kind='deadline-delay',syscall=spec['syscall'],nth=spec['nth'],baseline=spec['baseline'],hit=hit,
                                deadline_ms=5000,injected_delay_ms=6000,elapsed_ms=value['ms'],
                                state_after_fault=after_fault(tree,tag),recovery_ms=recover(tree,tag)))
            rename=next(s for s in schedule if s['kind']=='kill' and s['syscall']=='renameat2')
            for i,address in enumerate((policy_hash,receipt_hash)):
                tag='kill-then-loss-%d'%i
                with tempfile.TemporaryDirectory(prefix='nia-publication-stacked-') as temp:
                    tree=copy_base(temp);injection=f"renameat2:signal=SIGKILL:when={rename['nth']}"
                    value=invoke(tree,tag+'-kill',injection=injection)
                    hit=calls(value['trace'],'renameat2')[rename['nth']-1]
                    assert value['returncode']==-signal.SIGKILL and str(tree/'state') in hit and 'killed by SIGKILL' in value['trace']
                    path=object_path(tree/'store',address);held=tree/'withheld';path.rename(held)
                    before=inventory(tree);refuse(invoke(tree,tag+'-damaged'));assert inventory(tree)==before
                    held.rename(path)
                    record(dict(id=tag,kind='kill-then-loss',sha256=address,hit=hit,injection=injection,
                                explicit_lab_restore=True,recovery_ms=recover(tree,tag)))
            report['result']='pass';report['case_count']=len(report['cases'])
            report['counts']=dict(Counter(c['kind'] for c in report['cases']))
            durations=sorted(c['recovery_ms'] for c in report['cases'])
            report['recovery_ms']=dict(p50=durations[(len(durations)-1)//2],p95=durations[int((len(durations)-1)*.95)],max=max(durations))
            report['observed_false_successes']=0
        except BaseException as exc:
            report['result']='failed';report['failure']=repr(exc);persist();raise
        finally:
            report['completed_utc']=time.time();persist()
    print('PASS completed publication cases',report['case_count'])

if __name__=='__main__': main()
