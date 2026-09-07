# SPDX-License-Identifier: MIT
"""Authenticate an OFFLINE Debian snapshot without APT or host package writes.

Trust anchor policy is supplied independently, not taken from the mirror. This
validates intake at `now`; it is not authorization to execute or indefinitely
replay an expired snapshot. Existing accepted rollback generations use a separate
current Nia authorization, not an expiry bypass here. gpgv is external TCB.
"""
from __future__ import annotations
import datetime as dt, email.utils, os, re, subprocess, tempfile
from pathlib import Path
from nia_common import Invalid,fields,digest,integer,relative,read_at,read_file,sha
from deb_archive import deb822,decompress,inspect_bytes,MAX_DEB,unfold

MAX_RELEASE=16*1024*1024
MAX_INDEX=256*1024*1024
FPR=re.compile(r'(?:[A-F0-9]{40}|[A-F0-9]{64})\Z')
AUTH_FIELDS={'schema','keyring_sha256','primary_fingerprints','minimum_signatures','now','max_age_seconds','future_skew_seconds'}

def auth_policy(policy:dict):
    fields(policy,AUTH_FIELDS,'archive trust policy')
    if policy['schema']!='org.niaos.debian-trust/v1':raise Invalid('trust policy version')
    digest(policy['keyring_sha256'])
    fs=policy['primary_fingerprints']
    if not isinstance(fs,list) or not 1<=len(fs)<=16 or any(not isinstance(x,str) or not FPR.fullmatch(x) for x in fs) or len(set(fs))!=len(fs):raise Invalid('pinned primary fingerprints')
    integer(policy['minimum_signatures'],1,len(fs),'signature threshold')
    integer(policy['now'],1,2**53-1,'trusted time')
    integer(policy['max_age_seconds'],1,30*86400,'maximum intake age')
    integer(policy['future_skew_seconds'],0,300,'future clock tolerance')

def authenticated_release(signed:bytes,keyring:bytes,policy:dict)->tuple[bytes,list[str]]:
    auth_policy(policy)
    if len(signed)>MAX_RELEASE or sha(keyring)!=policy['keyring_sha256']:raise Invalid('keyring or signed release length mismatch')
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
                if stamp>policy['now']+policy['future_skew_seconds'] or (expiry and expiry<=policy['now']):raise Invalid('signature time invalid')
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
        if path in table or size>MAX_INDEX:raise Invalid('duplicate/oversized index')
        table[path]=(d,size)
    if not table:raise Invalid('empty SHA256 inventory')
    return table

def verify_snapshot(root:Path,keyring:bytes,policy:dict,index_path:str,deb_path:str)->dict:
    """One exact artifact, one exact authenticated index; no resolver completeness claim."""
    relative(index_path);relative(deb_path)
    match=re.fullmatch(r'(main|contrib|non-free|non-free-firmware)/binary-amd64/Packages(?:\.(gz|xz|zst))?',index_path)
    if not match or not deb_path.startswith('pool/') or not deb_path.endswith('.deb'):raise Invalid('unsupported snapshot paths')
    signed=read_at(root,'dists/forky/InRelease',MAX_RELEASE)
    release,signers=authenticated_release(signed,keyring,policy)
    paragraphs=deb822(release,limit=MAX_RELEASE,max_stanzas=1)
    if len(paragraphs)!=1:raise Invalid('Release stanza count')
    record=paragraphs[0]
    for key,expected in (('origin','Debian'),('label','Debian'),('codename','forky')):
        if record.get(key)!=expected:raise Invalid('different upstream identity: '+key)
    if record.get('suite') not in ('testing','stable'):raise Invalid('unqualified suite alias')
    if record.get('architectures','').split().count('amd64')!=1 or match[1] not in record.get('components','').split():raise Invalid('architecture/component absent')
    if not all(k in record for k in ('date','valid-until','sha256')):raise Invalid('Release freshness/SHA256 missing')
    date=release_date(record['date']);until=release_date(record['valid-until']);now=policy['now']
    if until<=date or now>=until or date>now+policy['future_skew_seconds'] or now-date>policy['max_age_seconds']:raise Invalid('expired/future/stale Release')
    table=hash_table(record['sha256'])
    if index_path not in table:raise Invalid('index not authenticated by Release')
    packed=read_at(root,'dists/forky/'+index_path,MAX_INDEX)
    if (sha(packed),len(packed))!=table[index_path]:raise Invalid('Packages checksum/length mismatch')
    extension=match[2]
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
    digest(package['sha256'])
    if not package['size'].isdigit() or int(package['size'])>MAX_DEB:raise Invalid('invalid indexed DEB size')
    content=read_at(root,deb_path,MAX_DEB)
    if len(content)!=int(package['size']) or sha(content)!=package['sha256']:raise Invalid('DEB not equal to authenticated archive bytes')
    observed=inspect_bytes(content)
    if tuple(observed['identity'][x] for x in ('package','version','architecture'))!=tuple(package[x] for x in ('package','version','architecture')):raise Invalid('index/header identity mismatch')
    # Resolver-relevant summaries must agree with the authenticated control archive.
    control=observed['fields']
    compared=('source','depends','pre-depends','conflicts','breaks','replaces','provides','multi-arch','essential','protected')
    for key in compared:
        if unfold(package.get(key,''))!=unfold(control.get(key,'')):raise Invalid('index/control semantic mismatch: '+key)
    observed['archive_authenticated']=True
    return {'schema':'org.niaos.intake-authentication/v1','execution_permit':False,
        'release_sha256':sha(release),'inrelease_sha256':sha(signed),'index_sha256':sha(packed),
        'primary_signers':signers,'accepted_at':now,'valid_until':until,'component':match[1],
        'source_family':'debian','codename':'forky','observation':observed,
        'dependency_universe_complete':False,'reproduced':False,'native_scripts_executed':False}

def verify_source(root:Path,keyring:bytes,policy:dict,binary_index:str,deb_path:str,source_index:str)->dict:
    """Authenticate complete Source checksum inventory in the SAME Release.

Archives are not unpacked, and .dsc signatures are not mistaken for reproduction.
This proves bytes named by Sources; it does not license them or execute a build.
"""
    from nia_common import hash_file_at,canonical
    from debian_semantics import split_version
    relative(source_index)
    match=re.fullmatch(r'(main|contrib|non-free|non-free-firmware)/source/Sources(?:\.(gz|xz|zst))?',source_index)
    if not match:raise Invalid('unsupported Sources path')
    binary=verify_snapshot(root,keyring,policy,binary_index,deb_path)
    if match[1]!=binary['component']:raise Invalid('cross-component source association')
    signed=read_at(root,'dists/forky/InRelease',MAX_RELEASE)
    if sha(signed)!=binary['inrelease_sha256']:raise Invalid('Release changed between binary/source observation')
    release,_=authenticated_release(signed,keyring,policy)
    record=deb822(release,limit=MAX_RELEASE,max_stanzas=1)[0]
    table=hash_table(record['sha256'])
    if source_index not in table:raise Invalid('Sources index not authenticated')
    packed=read_at(root,'dists/forky/'+source_index,MAX_INDEX)
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
    manifest={'schema':'org.niaos.source-manifest/v1','distribution':'debian','codename':'forky',
        'inrelease_sha256':binary['inrelease_sha256'],'sources_index_sha256':sha(packed),
        'name':source_name,'version':source_version,'dsc_sha256':dscs[0],
        'files':sorted(files,key=lambda x:x['path'])}
    return {'source_manifest':manifest,'source_manifest_sha256':sha(canonical(manifest)),
        'binary_sha256':binary['observation']['artifact_sha256'],'execution_permit':False,
        'source_authenticated':True,'source_rebuilt':False,'reproduced':False,
        'redistribution_rights_reviewed':False,'source_signature_separately_checked':False}
