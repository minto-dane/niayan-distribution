# SPDX-License-Identifier: BSD-3-Clause
"""Independent, exact-artifact reproduction receipts; never bless a package name.

Receipts report an observer's claim, not a proof that the rebuilder or source is
benign. Key registry/clock/revocation must come from current independent trust.
No production keys are shipped. Public rebuilder status is not a signed receipt.
"""
from __future__ import annotations
import base64,re
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from nia_common import Invalid,fields,integer,digest,canonical,sha
from deb_archive import deb822
from debian_semantics import split_version

DOMAIN=b'NiaOS/reproduction/v1\x00'
SUBJECT={'deb_sha256','source_manifest_sha256','buildinfo_sha256','package','version','architecture'}
BODY={'schema','subject','release_sha256','policy_sha256','rebuilder','domain','key_id','issued','expires','observed_sha256','method'}

def subject(value):
    fields(value,SUBJECT,'reproduction subject')
    for name in ('deb_sha256','source_manifest_sha256','buildinfo_sha256'):digest(value[name])
    if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]+',value['package']):raise Invalid('subject package')
    split_version(value['version'])
    if value['architecture'] not in ('amd64','all'):raise Invalid('subject architecture')

def check_buildinfo(raw:bytes,expected:dict)->dict:
    """Digest-bound .buildinfo proves only matching declared metadata, not reproduction."""
    subject(expected)
    if sha(raw)!=expected['buildinfo_sha256']:raise Invalid('different buildinfo object')
    data=deb822(raw)
    if len(data)!=1:raise Invalid('buildinfo paragraphs')
    info=data[0]
    if info.get('format')!='1.0' or expected['package'] not in info.get('binary','').split():raise Invalid('buildinfo binary set')
    if expected['architecture'] not in info.get('architecture','').split():raise Invalid('buildinfo architecture')
    # .buildinfo Version is the source version, potentially different from a
    # binNMU binary version. Bind exact binary via the checksum, never trim +bN.
    if not info.get('source') or not info.get('version') or not info.get('installed-build-depends'):raise Invalid('build environment/source missing')
    split_version(info['version'])
    matches=[];names=set()
    for line in info.get('checksums-sha256','').splitlines():
        if not line.strip():continue
        words=line.split()
        if len(words)!=3 or not words[1].isdigit() or '/' in words[2] or words[2] in names:raise Invalid('buildinfo checksum list')
        digest(words[0]);names.add(words[2])
        if words[0]==expected['deb_sha256'] and words[2].endswith('.deb'):matches.append(words)
    if len(matches)!=1:raise Invalid('exact binary not identified in buildinfo')
    return {'buildinfo_matches':True,'reproduced':False,'execution_permit':False,'source':info['source'],'source_version':info['version']}

def check_receipts(receipts:list,expected:dict,registry:dict,now:int,release:str,policy:str,threshold=2)->dict:
    subject(expected);digest(release);digest(policy);integer(now,1,2**53-1,'current time');integer(threshold,2,8,'reproduction threshold')
    if not isinstance(receipts,list) or len(receipts)>32:raise Invalid('receipt count')
    seen_keys=set();identities=set();domains=set();accepted=[]
    for envelope in receipts:
        fields(envelope,{'body','signature'},'receipt')
        body=envelope['body'];fields(body,BODY,'receipt body')
        if body['schema']!='org.niaos.reproduction/v1' or body['method']!='rebuild-official-binary':raise Invalid('receipt schema/method')
        subject(body['subject'])
        if body['subject']!=expected or body['release_sha256']!=release or body['policy_sha256']!=policy:raise Invalid('receipt scope mismatch')
        if body['observed_sha256']!=expected['deb_sha256']:raise Invalid('rebuild does not reproduce distributed binary')
        issued=integer(body['issued'],1,2**53-1,'issued');expires=integer(body['expires'],1,2**53-1,'expires')
        if not issued<=now<expires or expires-issued>30*86400:raise Invalid('receipt freshness')
        kid=body['key_id']
        if not isinstance(kid,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',kid):raise Invalid('key identifier')
        if kid in seen_keys or kid not in registry:raise Invalid('unknown/duplicate receipt key')
        key=registry[kid];fields(key,{'public_key','principal','domain','revoked','valid_from','valid_until'},'key registry entry')
        start=integer(key['valid_from'],1,2**53-1,'authority start');end=integer(key['valid_until'],1,2**53-1,'authority end')
        for name in ('principal','domain'):
            if not isinstance(key[name],str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',key[name]):raise Invalid('invalid registered identity')
        if key['revoked'] is not False or not start<=issued<=now<end:raise Invalid('revoked/expired authority')
        if body['rebuilder']!=key['principal'] or body['domain']!=key['domain']:raise Invalid('asserted independence differs from registry')
        if key['principal'] in identities or key['domain'] in domains:raise Invalid('non-independent rebuild witnesses')
        try:
            pub=bytes.fromhex(key['public_key']);sig=base64.b64decode(envelope['signature'],validate=True)
            if len(pub)!=32 or len(sig)!=64:raise Invalid('receipt key/signature size')
            Ed25519PublicKey.from_public_bytes(pub).verify(sig,DOMAIN+canonical(body))
        except (ValueError,InvalidSignature) as exc:raise Invalid('invalid reproduction signature') from exc
        seen_keys.add(kid);identities.add(key['principal']);domains.add(key['domain']);accepted.append(kid)
    if len(accepted)<threshold:raise Invalid('insufficient independently authorized reproduction evidence')
    return {'receipt_check':'pass','exact_artifact':expected['deb_sha256'],'independent_receipts':len(accepted),
            'execution_permit':False,'native_effects_verified':False,'source_correctness_proven':False}
