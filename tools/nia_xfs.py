# SPDX-License-Identifier: MIT
"""XFS product contract, closed evidence checks, and non-authorizing local inventory.

No ioctl, mount, formatting, repair, helper execution, service change, or network.
Inputs to assess() are observations, not signatures. Signature validation and
current ownership belong to the receiving high-assurance runtime, not this tool.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from nia_common import Invalid, canonical, fields, digest, relative

TRUTH = {'unknown', 'satisfied', 'violated'}
CAPABILITIES = ('scrub_readonly', 'online_repair', 'health_events', 'reverse_mapping', 'parent_pointers')
DISK_FEATURES = ('crc', 'finobt', 'inobtcount', 'bigtime', 'rmapbt', 'reflink', 'parent')
COHORT = ('kernel', 'kernel_config', 'xfsprogs', 'rescue_kernel', 'rescue_xfsprogs', 'disk_geometry', 'policy')
REPAIR_FACTS = ('independent_backup', 'rescue_compatible', 'isolated_evidence', 'single_writer_ownership',
                'bounded_budget', 'current_authorization', 'no_unresolved_operation', 'qualified_runtime',
                'experimental_feature_waiver', 'native_autorepair_disabled_outside_session')
SOURCE = Path(__file__).resolve().parents[1] / 'contracts/xfs-policy.json'
# Fixed contract values are independent of a caller's modified input file.
POLICY_FIELDS = {'schema','product','architecture','default_disk_filesystem','exceptions',
 'kernel_minimum','xfsprogs_minimum','version_is_capability_proof','kernel_features','disk_features',
 'capabilities','cohort','observer_mode','repair_policy','experimental_feature_waiver_required',
 'qualified_for_automatic_repair','event_owner','mount_scope','lost_events','unknown_event','media_error',
 'metadata_healthy_is_content_healthy','fsverity_assumed','integrity','snapshot_required','native_fs_multi_file_acid',
 'max_concurrent_scrubs_per_filesystem','max_online_repair_attempts','max_evidence_age_ms','max_scrub_age_seconds',
 'log_zeroing_allowed','mount_norecovery_allowed','generic_force_repair_allowed','repair_requires',
 'postrepair_requires','execution_permit','production_qualified'}

def check_policy(p: dict) -> dict:
    fields(p, POLICY_FIELDS, 'XFS product policy')
    expected = {
     'schema':'org.niaos.xfs-policy/v1','product':'nia-os','architecture':'x86_64',
     'default_disk_filesystem':'xfs','exceptions':{'efi':'vfat','volatile':'tmpfs','kernel':'virtual'},
     'kernel_minimum':[7,0,0],'xfsprogs_minimum':[7,0,0],
     'kernel_features':['CONFIG_XFS_FS','CONFIG_XFS_ONLINE_SCRUB','CONFIG_XFS_ONLINE_REPAIR'],
     'disk_features':list(DISK_FEATURES),'capabilities':list(CAPABILITIES),'cohort':list(COHORT),
     'observer_mode':'native-healer-no-autofsck','repair_policy':'explicit-qualified-session',
     'event_owner':'one-native-healer-per-filesystem',
     'mount_scope':'filesystem-uuid+mount-id+mount-namespace+boot-id',
     'lost_events':'invalidate-and-full-readonly-rescan','unknown_event':'invalidate-and-rescan',
     'media_error':'preserve-evidence-contain-and-restore-authenticated-content',
     'integrity':'authenticated-catalog-digests+independent-backup+application-checksums',
     'max_concurrent_scrubs_per_filesystem':1,'max_online_repair_attempts':2,
     'max_evidence_age_ms':5000,'max_scrub_age_seconds':691200,
     'repair_requires':['independent-backup','rescue-compatible','isolated-evidence','single-writer-ownership',
         'bounded-budget','current-authorization','no-media-error','no-unresolved-operation'],
     'postrepair_requires':['new-full-metadata-scrub','catalog-content-and-attribute-verification',
         'configuration-validation','application-health','fresh-independent-acceptance'],
    }
    for key in ('version_is_capability_proof','qualified_for_automatic_repair','metadata_healthy_is_content_healthy',
                'fsverity_assumed','snapshot_required','native_fs_multi_file_acid','log_zeroing_allowed',
                'mount_norecovery_allowed','generic_force_repair_allowed','execution_permit','production_qualified'):
        expected[key] = False
    expected['experimental_feature_waiver_required'] = True
    if canonical(p) != canonical(expected): raise Invalid('unreviewed XFS policy change')
    return {'policy_valid': True, 'execution_permit': False, 'production_qualified': False}

def _uint(v, maximum=(1 << 63)-1):
    if type(v) is not int or not 0 <= v <= maximum: raise Invalid('invalid bounded integer')
    return v

def _truth_map(v, keys):
    fields(v, set(keys), 'capability facts')
    if any(not isinstance(x, str) or x not in TRUTH for x in v.values()): raise Invalid('invalid/unknown truth encoding')

def _version(s):
    if not isinstance(s, str) or not re.fullmatch(r'[0-9]{1,4}\.[0-9]{1,4}(?:\.[0-9]{1,4})?', s):
        raise Invalid('version must be normalized by the artifact adapter')
    x = [int(v) for v in s.split('.')]
    return tuple(x + [0] * (3-len(x)))

def assess(policy: dict, observation: dict, expected: dict, now_ms: int) -> dict:
    """Strictly bound diagnostic assessment. Never grants authority to execute."""
    check_policy(policy); _uint(now_ms)
    fields(expected, {'node','boot','fs_uuid','mount_id','mount_namespace','cohort'}, 'expected subject')
    fields(observation, {'schema','subject','observed_ms','expires_ms','kernel_version','xfsprogs_version',
        'capabilities','disk_features','repair_facts','metadata','media','content','stream_complete',
        'last_event_sequence','scrub_covers_sequence','scrub_started_ms','scrub_finished_ms',
        'repair_attempts','unresolved_operation'}, 'XFS observation')
    if observation['schema'] != 'org.niaos.xfs-observation/v1': raise Invalid('XFS observation schema')
    subject = observation['subject']
    fields(subject, set(expected), 'observed subject')
    fields(expected['cohort'], set(COHORT), 'expected cohort')
    fields(subject['cohort'], set(COHORT), 'observed cohort')
    for s in (expected, subject):
        for key in ('node','boot','fs_uuid'):
            if not isinstance(s[key], str) or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', s[key]):
                raise Invalid('noncanonical subject identifier')
            if s[key] == '00000000-0000-0000-0000-000000000000': raise Invalid('zero subject identifier')
        for key in ('mount_id','mount_namespace'):
            if _uint(s[key]) == 0: raise Invalid('unknown mount identity')
        for h in s['cohort'].values():
            digest(h)
            if h == '0'*64: raise Invalid('unbound cohort')
    if expected['cohort']['policy'] != hashlib.sha256(canonical(policy)).hexdigest():
        raise Invalid('policy digest does not identify this contract')
    if canonical(subject) != canonical(expected): raise Invalid('filesystem/cohort/boot binding mismatch')
    a, b = _uint(observation['observed_ms']), _uint(observation['expires_ms'])
    if not a <= now_ms < b or b-a > policy['max_evidence_age_ms'] or now_ms-a > policy['max_evidence_age_ms']:
        raise Invalid('stale/future XFS observation')
    _truth_map(observation['capabilities'], CAPABILITIES)
    _truth_map(observation['disk_features'], DISK_FEATURES)
    _truth_map(observation['repair_facts'], REPAIR_FACTS)
    for key in ('metadata','media','content'):
        if not isinstance(observation[key], str) or observation[key] not in TRUTH:
            raise Invalid('invalid integrity axis')
    for key in ('stream_complete','unresolved_operation'):
        if type(observation[key]) is not bool: raise Invalid('noncanonical boolean')
    for key in ('last_event_sequence','scrub_covers_sequence','scrub_started_ms','scrub_finished_ms','repair_attempts'):
        _uint(observation[key])
    if observation['scrub_covers_sequence'] > observation['last_event_sequence']:
        raise Invalid('scrub references an unobserved event')
    if observation['scrub_finished_ms'] > now_ms or observation['scrub_started_ms'] > observation['scrub_finished_ms']:
        raise Invalid('invalid scrub interval')
    missing = []
    if _version(observation['kernel_version']) < tuple(policy['kernel_minimum']): missing.append('kernel-floor')
    if _version(observation['xfsprogs_version']) < tuple(policy['xfsprogs_minimum']): missing.append('xfsprogs-floor')
    for group in ('capabilities','disk_features'):
        missing += [group+'.'+k for k,v in observation[group].items() if v != 'satisfied']
    full_scan = (observation['scrub_finished_ms'] > 0 and
        now_ms - observation['scrub_finished_ms'] <= policy['max_scrub_age_seconds']*1000 and
        observation['scrub_covers_sequence'] == observation['last_event_sequence'])
    if observation['media'] == 'violated' or observation['content'] == 'violated':
        action = 'contain-preserve-and-plan-content-recovery'
    elif observation['unresolved_operation']:
        action = 'reconcile-existing-operation'
    elif missing:
        action = 'hold-new-changes-capability-gap'
    elif not observation['stream_complete']:
        action = 'reestablish-stream-and-full-readonly-scrub'
    elif observation['metadata'] == 'violated':
        ready = all(v == 'satisfied' for v in observation['repair_facts'].values())
        ready = ready and observation['media'] == 'satisfied' and observation['content'] == 'satisfied'
        ready = ready and observation['repair_attempts'] < policy['max_online_repair_attempts']
        action = 'qualified-repair-session-candidate' if ready else 'preserve-evidence-and-plan-offline-recovery'
    elif observation['metadata'] != 'satisfied' or not full_scan:
        action = 'schedule-full-readonly-scrub'
    elif observation['media'] != 'satisfied' or observation['content'] != 'satisfied':
        action = 'hold-new-changes-content-or-media-unverified'
    else:
        action = 'metadata-media-content-candidate-consistent'
    return {'schema':'org.niaos.xfs-assessment/v1','action':action,'missing':missing,
        'execution_permit':False,'production_qualified':False,'facts_authenticated':False,
        'metadata_clean_authenticates_content':False,'signature_and_runtime_gate_required':True}

_ESCAPE = re.compile(r'\\([0-7]{3})')
def _mount_unescape(s):
    out = _ESCAPE.sub(lambda m: chr(int(m.group(1),8)), s)
    if '\x00' in out or any(ord(c) < 32 for c in out): raise Invalid('invalid mount field')
    return out

def parse_mountinfo(data: bytes) -> list[dict]:
    if len(data) > 4*1024*1024: raise Invalid('mountinfo too large')
    rows=[]; ids=set()
    for line in data.decode('utf-8','strict').splitlines():
        parts = line.split(' ')
        if parts.count('-') != 1: raise Invalid('mountinfo delimiter')
        k = parts.index('-')
        if k < 6 or len(parts) != k+4: raise Invalid('mountinfo field count')
        if not all(re.fullmatch(r'[0-9]+',parts[i]) for i in (0,1)) or not re.fullmatch(r'[0-9]+:[0-9]+',parts[2]):
            raise Invalid('mountinfo numeric fields')
        mid=int(parts[0])
        if mid in ids or mid == 0 or mid > (1<<64)-1: raise Invalid('mount id ambiguity')
        ids.add(mid)
        row={'mount_id':mid,'parent_id':int(parts[1]),'device':parts[2],
             'root':_mount_unescape(parts[3]),'mount_point':_mount_unescape(parts[4]),
             'options':parts[5].split(','),'filesystem':parts[k+1],
             'source':_mount_unescape(parts[k+2]),'super_options':parts[k+3].split(',')}
        # The kernel may report a bind mount's root outside the process root
        # as /../... in a mount namespace (including Distrobox). It is opaque
        # inventory data, never a path to open or an authorization input.
        if not row['root'].startswith('/'): raise Invalid('relative mount root')
        if not row['mount_point'].startswith('/'): raise Invalid('relative mount path')
        if row['mount_point'] != '/': relative(row['mount_point'][1:])
        rows.append(row)
        if len(rows)>16384: raise Invalid('too many mounts')
    return rows

def _read_proc(path: str, limit: int) -> bytes:
    # Private constant path only. procfs may have st_size == 0 and still return data.
    fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
    try:
        chunks=[]; total=0
        while True:
            b=os.read(fd,min(65536,limit+1-total))
            if not b: break
            total+=len(b)
            if total>limit: raise Invalid('proc observation size limit')
            chunks.append(b)
        return b''.join(chunks)
    finally: os.close(fd)

def _open_directory(path: str) -> int:
    if not isinstance(path,str) or not path.startswith('/'): raise Invalid('absolute directory required')
    if path != '/': relative(path[1:])
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        for part in path.split('/')[1:]:
            if not part: continue
            nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=nxt
        return fd
    except BaseException:
        os.close(fd); raise

def inspect_local(mountpoint: str) -> dict:
    """Read a pinned mount and mountinfo twice. Absence of errors is not a scrub."""
    started=time.monotonic_ns()
    before=_read_proc('/proc/self/mountinfo',4*1024*1024)
    ns=os.stat('/proc/self/ns/mnt').st_ino
    rows=parse_mountinfo(before)
    matches=[r for r in rows if r['mount_point']==mountpoint]
    if len(matches)!=1: raise Invalid('not a unique exact mount point')
    r=matches[0]
    fd=_open_directory(mountpoint)
    try:
        st=os.fstat(fd);v=os.fstatvfs(fd)
        info=_read_proc('/proc/self/fdinfo/'+str(fd),8192).decode()
        mids=re.findall(r'^mnt_id:\s*([0-9]+)$',info,re.M)
        if len(mids)!=1 or int(mids[0])!=r['mount_id']: raise Invalid('pinned directory is a different mount')
        if f'{os.major(st.st_dev)}:{os.minor(st.st_dev)}'!=r['device']: raise Invalid('mount device changed')
        after=_read_proc('/proc/self/mountinfo',4*1024*1024)
        if before!=after or os.stat('/proc/self/ns/mnt').st_ino!=ns: raise Invalid('mount topology changed during observation')
        boot=_read_proc('/proc/sys/kernel/random/boot_id',128).decode().strip()
        return {'schema':'org.niaos.xfs-local-inventory/v1','mount':r,'mount_namespace':ns,
          'boot_id':boot,'kernel_release':os.uname().release,'observed_mono_ns':started,
          'finished_mono_ns':time.monotonic_ns(),'available_bytes':v.f_bavail*v.f_frsize,
          'available_inodes':v.f_favail,'readonly':bool(v.f_flag & os.ST_RDONLY),
          'xfs_mount_observed':r['filesystem']=='xfs','geometry':'not-probed','healthmon':'not-probed',
          'online_repair':'not-probed','metadata_health':'unknown','content_integrity':'unknown',
          'evidence_authenticated':False,'execution_permit':False,'production_qualified':False}
    finally: os.close(fd)
