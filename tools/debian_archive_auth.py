# SPDX-License-Identifier: BSD-3-Clause
"""Authenticate an OFFLINE Debian snapshot without APT or host package writes.

Trust anchor policy is supplied independently, not taken from the mirror. This
validates intake at `now`; it is not authorization to execute or indefinitely
replay an expired snapshot. Existing accepted rollback generations use a separate
current Nia authorization, not an expiry bypass here. gpgv is external TCB.
"""
from __future__ import annotations
import datetime as dt, email.utils, os, re, subprocess, tempfile
from pathlib import Path
from nia_common import Invalid,fields,digest,integer,relative,read_at,read_file,sha,canonical
from deb_archive import deb822,decompress,inspect_bytes,MAX_DEB,unfold

MAX_RELEASE=16*1024*1024
MAX_INDEX=256*1024*1024
FPR=re.compile(r'(?:[A-F0-9]{40}|[A-F0-9]{64})\Z')
AUTH_FIELDS={'schema','keyring_sha256','primary_fingerprints','minimum_signatures','now','max_age_seconds','future_skew_seconds'}
RELEASE_FIELDS={'codename','suite','architecture','components','inrelease_sha256','minimum_date','expires'}
COMPONENTS={'main','contrib','non-free','non-free-firmware'}
POCKETS={'trixie':'', 'trixie-updates':'-updates', 'trixie-security':'-security', 'trixie-backports':'-backports'}

def auth_policy(policy:dict):
    if type(policy) is not dict:raise Invalid('archive trust policy type')
    version=policy.get('schema')
    if version not in ('org.niaos.debian-trust/v1','org.niaos.debian-trust/v2'):raise Invalid('trust policy version')
    legacy=version.endswith('/v1')
    fields(policy,AUTH_FIELDS if legacy else AUTH_FIELDS-{'now'}|{'release'},'archive trust policy')
    digest(policy['keyring_sha256'])
    fs=policy['primary_fingerprints']
    if not isinstance(fs,list) or not 1<=len(fs)<=16 or any(not isinstance(x,str) or not FPR.fullmatch(x) for x in fs) or len(set(fs))!=len(fs):raise Invalid('pinned primary fingerprints')
    integer(policy['minimum_signatures'],1,len(fs),'signature threshold')
    if legacy:integer(policy['now'],1,2**53-1,'trusted time')
    integer(policy['max_age_seconds'],1,(30 if legacy else 366)*86400,'maximum intake age')
    integer(policy['future_skew_seconds'],0,300,'future clock tolerance')
    if not legacy:
        r=policy['release'];fields(r,RELEASE_FIELDS,'pinned Release policy')
        if not isinstance(r['codename'],str) or r['codename'] not in POCKETS:raise Invalid('unsupported pinned codename')
        if r['suite'] not in tuple(s+POCKETS[r['codename']] for s in ('stable','oldstable','oldoldstable')):raise Invalid('suite does not match pinned pocket')
        if not isinstance(r['architecture'],str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,31}',r['architecture']) or r['architecture']=='all':raise Invalid('binary index architecture')
        cs=r['components']
        if not isinstance(cs,list) or not 1<=len(cs)<=4 or any(not isinstance(c,str) or c not in COMPONENTS for c in cs) or cs!=sorted(set(cs)):raise Invalid('canonical component policy')
        digest(r['inrelease_sha256'])
        integer(r['minimum_date'],1,2**53-1,'independent Release date floor')
        integer(r['expires'],r['minimum_date']+1,2**53-1,'independent intake expiry')
        if r['codename']!='trixie' and policy['max_age_seconds']>30*86400:raise Invalid('update pocket age limit')

def _context(policy:dict,now:int|None):
    auth_policy(policy)
    if policy['schema'].endswith('/v1'):
        if now is not None:raise Invalid('legacy time must come from legacy policy')
        return {'codename':'forky','architecture':'amd64','components':sorted(COMPONENTS)},policy['now']
    integer(now,1,2**53-1,'independently observed time')
    if now>=policy['release']['expires']:raise Invalid('pinned intake policy expired')
    return policy['release'],now

def authenticated_release(signed:bytes,keyring:bytes,policy:dict,*,now:int|None=None)->tuple[bytes,list[str]]:
    profile,clock=_context(policy,now)
    if len(signed)>MAX_RELEASE or sha(keyring)!=policy['keyring_sha256']:raise Invalid('keyring or signed release length mismatch')
    if 'inrelease_sha256' in profile and sha(signed)!=profile['inrelease_sha256']:raise Invalid('InRelease differs from independent pin')
    if not signed.startswith(b'-----BEGIN PGP SIGNED MESSAGE-----\n'):raise Invalid('only InRelease clear signatures accepted')
    with tempfile.TemporaryDirectory(prefix='nia-gpgv-') as temp:
        root=Path(temp);os.chmod(root,0o700)
        (root/'archive.gpg').write_bytes(keyring);(root/'InRelease').write_bytes(signed)
        # Input bytes were securely read and are now immutable private copies.
        # No trustdb, key retrieval, ambient GNUPGHOME, or shell execution.
        with (root/'status').open('wb') as status, (root/'stderr').open('wb') as error:
            try:
                result=subprocess.run(['/usr/bin/gpgv','--homedir',str(root),'--keyring',str(root/'archive.gpg'),
                    '--status-fd','1','--output',str(root/'Release'),str(root/'InRelease')],stdout=status,stderr=error,
                    env={'PATH':'/usr/bin:/bin','LC_ALL':'C','HOME':str(root)},timeout=30,check=False)
            except (OSError,subprocess.TimeoutExpired) as exc:raise Invalid('gpgv unavailable or timeout') from exc
        text=read_file(root/'status',1024*1024).decode('ascii',errors='strict')
        if result.returncode!=0:raise Invalid('archive signature validation failed')
        good=set()
        fatal={'BADSIG','ERRSIG','EXPSIG','EXPKEYSIG','REVKEYSIG','NO_PUBKEY','NODATA','FAILURE'}
        for line in text.splitlines():
            if not line.startswith('[GNUPG:] '):raise Invalid('unexpected gpgv status output')
            words=line[9:].split()
            if not words:raise Invalid('empty gpgv status')
            if words[0] in fatal:raise Invalid('archive signature error status')
            if words[0]=='VALIDSIG':
                # VALIDSIG signer date ts expire ver reserved pk_algo hash_algo class [primary]
                if len(words) not in (10,11):raise Invalid('unknown VALIDSIG schema')
                primary=words[10] if len(words)==11 else words[1]
                if primary not in policy['primary_fingerprints']:raise Invalid('untrusted archive signer')
                if words[8] not in ('8','9','10') or words[9]!='01':raise Invalid('weak digest or non-text signature')
                try:stamp=int(words[3]);expiry=int(words[4])
                except ValueError as exc:raise Invalid('signature timestamps') from exc
                if stamp>clock+policy['future_skew_seconds'] or (expiry and expiry<=clock):raise Invalid('signature time invalid')
                good.add(primary)
        if len(good)<policy['minimum_signatures']:raise Invalid('insufficient independent archive signatures')
        return read_file(root/'Release',MAX_RELEASE),sorted(good)

def release_date(value:str)->int:
    try:
        parsed=email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:raise Invalid('unqualified timezone')
        return int(parsed.timestamp())
    except (ValueError,TypeError,OverflowError) as exc:raise Invalid('invalid Release date') from exc

def hash_table(text:str)->dict[str,tuple[str,int]]:
    table={}
    for row in text.splitlines():
        if not row.strip():continue
        parts=row.split()
        if len(parts)!=3 or not parts[1].isdigit():raise Invalid('invalid SHA256 metadata row')
        d,n,path=parts;digest(d);relative(path);size=int(n)
        # Release also lists unrelated, very large Contents files. Their sizes
        # are metadata, not allocation requests. Bound actual selected reads.
        if path in table or size>2**63-1:raise Invalid('duplicate/oversized index size')
        table[path]=(d,size)
    if not table:raise Invalid('empty SHA256 inventory')
    return table

def _read_release(root:Path,keyring:bytes,policy:dict,now:int|None):
    profile,clock=_context(policy,now)
    signed=read_at(root,'dists/'+profile['codename']+'/InRelease',MAX_RELEASE)
    release,signers=authenticated_release(signed,keyring,policy,now=now)
    paragraphs=deb822(release,limit=MAX_RELEASE,max_stanzas=1)
    if len(paragraphs)!=1:raise Invalid('Release stanza count')
    record=paragraphs[0]
    label='Debian-Security' if profile['codename']=='trixie-security' else 'Debian'
    for key,expected in (('origin','Debian'),('label',label),('codename',profile['codename'])):
        if record.get(key)!=expected:raise Invalid('different upstream identity: '+key)
    suites=(profile['suite'],) if 'suite' in profile else ('testing','stable')
    if record.get('suite') not in suites:raise Invalid('unqualified suite alias')
    if record.get('architectures','').split().count(profile['architecture'])!=1:raise Invalid('architecture absent')
    if not all(k in record for k in ('date','sha256')):raise Invalid('Release freshness/SHA256 missing')
    date=release_date(record['date']);until=date+policy['max_age_seconds']
    if 'valid-until' in record:
        upstream_until=release_date(record['valid-until'])
        if upstream_until<=date:raise Invalid('invalid Release validity interval')
        until=min(until,upstream_until)
    elif profile['codename']!='trixie':raise Invalid('Release Valid-Until missing')
    if 'expires' in profile:
        until=min(until,profile['expires'])
        if date<profile['minimum_date']:raise Invalid('Release below independent date floor')
    if clock>=until or date>clock+policy['future_skew_seconds']:raise Invalid('expired/future/stale Release')
    return profile,clock,signed,release,signers,record,until

def verify_release(root:Path,keyring:bytes,policy:dict,*,now:int|None=None)->dict:
    """Authenticate Release identity/freshness only; no package or execution grant."""
    profile,clock,signed,release,signers,record,until=_read_release(root,keyring,policy,now)
    hash_table(record['sha256'])
    return {'schema':'org.niaos.release-authentication/v1','execution_permit':False,
            'inrelease_sha256':sha(signed),'release_sha256':sha(release),'policy_sha256':sha(canonical(policy)),
            'primary_signers':signers,'codename':profile['codename'],'suite':record['suite'],
            'accepted_at':clock,'valid_until':until,'upstream_valid_until':record.get('valid-until'),
            'artifacts_authenticated':False}

def verify_snapshot(root:Path,keyring:bytes,policy:dict,index_path:str,deb_path:str,*,now:int|None=None)->dict:
    """One exact artifact, one exact authenticated index; no resolver completeness claim."""
    relative(index_path);relative(deb_path)
    match=re.fullmatch(r'(main|contrib|non-free|non-free-firmware)/binary-([a-z0-9][a-z0-9-]{0,31})/Packages(?:\.(gz|xz|zst))?',index_path)
    if not match or not deb_path.startswith('pool/') or not deb_path.endswith('.deb'):raise Invalid('unsupported snapshot paths')
    profile,clock,signed,release,signers,record,until=_read_release(root,keyring,policy,now)
    # The security archive declares updates/main etc.; its hashed index paths
    # are main/... . This mapping is specific to the pinned security pocket.
    declared=('updates/' if profile['codename']=='trixie-security' else '')+match[1]
    if match[2]!=profile['architecture'] or match[1] not in profile['components'] or record.get('components','').split().count(declared)!=1:raise Invalid('index outside architecture/component policy')
    table=hash_table(record['sha256'])
    if index_path not in table:raise Invalid('index not authenticated by Release')
    if table[index_path][1]>MAX_INDEX:raise Invalid('selected Packages byte limit')
    packed=read_at(root,'dists/'+profile['codename']+'/'+index_path,MAX_INDEX)
    if (sha(packed),len(packed))!=table[index_path]:raise Invalid('Packages checksum/length mismatch')
    extension=match[3]
    raw=decompress('data.tar.'+extension,packed,MAX_INDEX) if extension else packed
    packages=deb822(raw,limit=MAX_INDEX)
    matches=[];seen=set()
    for row in packages:
        identity=tuple(row.get(x,'') for x in ('package','version','architecture'))
        if identity in seen:raise Invalid('duplicate Packages identity')
        seen.add(identity)
        if row.get('filename')==deb_path:matches.append(row)
    if len(matches)!=1:raise Invalid('artifact absent or ambiguous in Packages')
    package=matches[0]
    if not all(k in package for k in ('package','version','architecture','filename','size','sha256')):raise Invalid('incomplete package index')
    if package['architecture'] not in (profile['architecture'],'all'):raise Invalid('indexed package architecture mismatch')
    digest(package['sha256'])
    if not package['size'].isdigit() or int(package['size'])>MAX_DEB:raise Invalid('invalid indexed DEB size')
    content=read_at(root,deb_path,MAX_DEB)
    if len(content)!=int(package['size']) or sha(content)!=package['sha256']:raise Invalid('DEB not equal to authenticated archive bytes')
    observed=inspect_bytes(content,architecture=profile['architecture'])
    if tuple(observed['identity'][x] for x in ('package','version','architecture'))!=tuple(package[x] for x in ('package','version','architecture')):raise Invalid('index/header identity mismatch')
    # Resolver-relevant summaries must agree with the authenticated control archive.
    control=observed['fields']
    compared=('source','depends','pre-depends','conflicts','breaks','replaces','provides','multi-arch','essential','protected')
    for key in compared:
        if unfold(package.get(key,''))!=unfold(control.get(key,'')):raise Invalid('index/control semantic mismatch: '+key)
    observed['archive_authenticated']=True
    return {'schema':'org.niaos.intake-authentication/v1','execution_permit':False,
        'release_sha256':sha(release),'inrelease_sha256':sha(signed),'index_sha256':sha(packed),
        'primary_signers':signers,'accepted_at':clock,'valid_until':until,'component':match[1],
        'source_family':'debian','codename':profile['codename'],'observation':observed,
        'dependency_universe_complete':False,'reproduced':False,'native_scripts_executed':False}

def verify_source(root:Path,keyring:bytes,policy:dict,binary_index:str,deb_path:str,source_index:str,*,now:int|None=None)->dict:
    """Authenticate complete Source checksum inventory in the SAME Release.

Archives are not unpacked, and .dsc signatures are not mistaken for reproduction.
This proves bytes named by Sources; it does not license them or execute a build.
"""
    from nia_common import hash_file_at,canonical
    from debian_semantics import split_version
    relative(source_index)
    match=re.fullmatch(r'(main|contrib|non-free|non-free-firmware)/source/Sources(?:\.(gz|xz|zst))?',source_index)
    if not match:raise Invalid('unsupported Sources path')
    binary=verify_snapshot(root,keyring,policy,binary_index,deb_path,now=now)
    if match[1]!=binary['component']:raise Invalid('cross-component source association')
    signed=read_at(root,'dists/'+binary['codename']+'/InRelease',MAX_RELEASE)
    if sha(signed)!=binary['inrelease_sha256']:raise Invalid('Release changed between binary/source observation')
    release,_=authenticated_release(signed,keyring,policy,now=now)
    record=deb822(release,limit=MAX_RELEASE,max_stanzas=1)[0]
    table=hash_table(record['sha256'])
    if source_index not in table:raise Invalid('Sources index not authenticated')
    if table[source_index][1]>MAX_INDEX:raise Invalid('selected Sources byte limit')
    packed=read_at(root,'dists/'+binary['codename']+'/'+source_index,MAX_INDEX)
    if (sha(packed),len(packed))!=table[source_index]:raise Invalid('Sources checksum/size mismatch')
    raw=decompress('data.tar.'+match[2],packed,MAX_INDEX) if match[2] else packed
    identity=binary['observation']['identity'];control=binary['observation']['fields']
    source=control.get('source',identity['package'])
    parsed=re.fullmatch(r'([a-z0-9][a-z0-9+.-]+)(?:\s+\(([^()\s]+)\))?',source)
    if not parsed:raise Invalid('Source identity syntax')
    source_name=parsed[1];source_version=parsed[2] or identity['version'];split_version(source_version)
    selected=[r for r in deb822(raw,limit=MAX_INDEX) if r.get('package')==source_name and r.get('version')==source_version]
    if len(selected)!=1:raise Invalid('source version absent or ambiguous')
    s=selected[0];directory=relative(s.get('directory',''))
    if not directory.startswith('pool/') or not s.get('checksums-sha256'):raise Invalid('source directory/checksums')
    binaries=[x.strip() for x in s.get('binary','').split(',')]
    if identity['package'] not in binaries:raise Invalid('binary not declared by source index')
    files=[];names=set();dscs=[];total=0
    for line in s['checksums-sha256'].splitlines():
        if not line.strip():continue
        row=line.split()
        if len(row)!=3 or not row[1].isdigit():raise Invalid('source checksum syntax')
        h,size,name=row;digest(h);relative(name)
        if '/' in name or name in names or len(names)>=256:raise Invalid('source member path/count')
        names.add(name);n=int(size);total+=n
        if n>8*1024**3 or total>32*1024**3:raise Invalid('source byte budget')
        path=directory+'/'+name
        if hash_file_at(root,path,n)!=(h,n):raise Invalid('source member checksum/length mismatch')
        files.append({'path':path,'size':n,'sha256':h})
        if name.endswith('.dsc'):dscs.append(h)
    if len(dscs)!=1 or not files:raise Invalid('exactly one source control object required')
    manifest={'schema':'org.niaos.source-manifest/v1','distribution':'debian','codename':binary['codename'],
        'inrelease_sha256':binary['inrelease_sha256'],'sources_index_sha256':sha(packed),
        'name':source_name,'version':source_version,'dsc_sha256':dscs[0],
        'files':sorted(files,key=lambda x:x['path'])}
    return {'source_manifest':manifest,'source_manifest_sha256':sha(canonical(manifest)),
        'binary_sha256':binary['observation']['artifact_sha256'],'execution_permit':False,
        'source_authenticated':True,'source_rebuilt':False,'reproduced':False,
        'redistribution_rights_reviewed':False,'source_signature_separately_checked':False}
