# SPDX-License-Identifier: MIT
"""Native DEB semantics for offline comparison. Never delegates trust to libsolv.

Single amd64/all binary input profile. Explicit foreign-architecture requests are
unsupported, not silently flattened. The SPARK comparator is independently coded.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from nia_common import Invalid

NAME=re.compile(r'[a-z0-9][a-z0-9+.-]+\Z')
VER=re.compile(r'(?:(?P<epoch>[0-9]+):)?(?P<rest>[0-9][A-Za-z0-9.+:~\-]*)\Z')
MAX_VERSION=512

def split_version(value: str):
    if not isinstance(value,str) or not 1<=len(value)<=MAX_VERSION:
        raise Invalid('version size')
    m=VER.fullmatch(value)
    if not m: raise Invalid('invalid Debian version')
    epoch=m.group('epoch') or '0';rest=m.group('rest')
    if int(epoch)>2147483647:raise Invalid('epoch exceeds dpkg-compatible supported range')
    if m.group('epoch') is None and ':' in rest: raise Invalid('colon without epoch')
    if '-' in rest:
        upstream,revision=rest.rsplit('-',1)
        if not revision or not re.fullmatch(r'[A-Za-z0-9+.~]+',revision):raise Invalid('invalid revision')
    else:upstream,revision=rest,'0'
    if not upstream:raise Invalid('empty upstream version')
    return epoch.lstrip('0') or '0',upstream,revision

def _digits(a,b):
    a=a.lstrip('0');b=b.lstrip('0')
    return (len(a)>len(b))-(len(a)<len(b)) or (a>b)-(a<b)

def _order(c):
    if c=='~':return -1
    if not c or '0'<=c<='9':return 0
    if 'A'<=c<='Z' or 'a'<=c<='z':return ord(c)
    return ord(c)+256

def _part(a,b):
    i=j=0
    while i<len(a) or j<len(b):
        while (i<len(a) and not a[i].isdigit()) or (j<len(b) and not b[j].isdigit()):
            x=_order(a[i] if i<len(a) else '');y=_order(b[j] if j<len(b) else '')
            if x!=y:return (x>y)-(x<y)
            if i<len(a):i+=1
            if j<len(b):j+=1
        start_i,start_j=i,j
        while i<len(a) and a[i].isdigit():i+=1
        while j<len(b) and b[j].isdigit():j+=1
        result=_digits(a[start_i:i],b[start_j:j])
        if result:return result
    return 0

def compare(a: str,b: str)->int:
    ea,ua,ra=split_version(a);eb,ub,rb=split_version(b)
    return _digits(ea,eb) or _part(ua,ub) or _part(ra,rb)

@dataclass(frozen=True)
class Atom:
    name:str
    architecture:str='unqualified'
    operator:str=''
    version:str=''

ATOM=re.compile(r'([a-z0-9][a-z0-9+.-]+)(?::(any|native|amd64))?\s*(?:\(\s*(<<|<=|=|>=|>>)\s*([^()\s]+)\s*\))?\s*\Z')

def relations(value: str, *, provides=False, alternatives=True)->tuple[tuple[Atom,...],...]:
    if not isinstance(value,str) or len(value)>65536:raise Invalid('relation size')
    if not value.strip():return ()
    groups=[];total=0
    for group in value.split(','):
        atoms=[]
        for item in group.split('|'):
            m=ATOM.fullmatch(item.strip())
            if not m:raise Invalid('unsupported or invalid binary relationship')
            name,arch,op,version=m.groups()
            if provides and (arch is not None or (op is not None and op!='=')):
                raise Invalid('Provides accepts only unqualified name and optional equality')
            if version:split_version(version)
            atoms.append(Atom(name,arch or 'unqualified',op or '',version or ''))
            total+=1
            if total>1024:raise Invalid('too many relation atoms')
        if (provides or not alternatives) and len(atoms)!=1:raise Invalid('alternatives forbidden in this field')
        groups.append(tuple(atoms))
    return tuple(groups)

def satisfies_version(provided: str|None, atom:Atom)->bool:
    if not atom.operator:return True
    if provided is None:return False # Unversioned Provides never satisfies a versioned need.
    value=compare(provided,atom.version)
    return {'<<':value<0,'<=':value<=0,'=':value==0,'>=':value>=0,'>>':value>0}[atom.operator]

def provider_matches(provider:dict, atom:Atom)->bool:
    if provider['architecture'] not in ('amd64','all'):raise Invalid('foreign architecture is not qualified')
    ma=provider.get('multi_arch','no')
    if ma not in ('no','same','foreign','allowed'):raise Invalid('unknown Multi-Arch mode')
    if atom.architecture=='any' and ma != 'allowed':return False
    # In the initial single-native-architecture profile native/exact/unqualified
    # all refer to amd64 or architecture-independent data. Foreign co-installation
    # and its SAME-version/shared-path rules are a distinct future profile.
    if provider['name']==atom.name and satisfies_version(provider['version'],atom):return True
    for name,version in provider.get('provides',[]):
        if name==atom.name and satisfies_version(version,atom):return True
    return False

def check_final(candidates:list[dict], selected:set[str])->dict:
    """Checks native final-state semantics, never an executable schedule proof."""
    ids=[p['id'] for p in candidates]
    if len(ids)!=len(set(ids)) or not selected.issubset(ids):raise Invalid('unknown or duplicate candidate')
    chosen=[p for p in candidates if p['id'] in selected]
    identities=[p['name'] for p in chosen]
    if len(identities)!=len(set(identities)):raise Invalid('same-name binary coinstallation is not qualified (including all/amd64)')
    for package in chosen:
        if package['architecture'] not in ('amd64','all'):raise Invalid('unqualified architecture')
        split_version(package['version'])
        for field in ('depends','pre_depends'):
            for group in relations(package.get(field,'')):
                if not any(provider_matches(other,atom) for atom in group for other in chosen):
                    raise Invalid('unsatisfied '+field+': '+package['name'])
        for field in ('conflicts','breaks'):
            for group in relations(package.get(field,''),alternatives=False):
                # Self-conflicts/Breaks on own Provides do not exclude the owner.
                if any(other['id']!=package['id'] and provider_matches(other,group[0]) for other in chosen):
                    raise Invalid(field+': '+package['name'])
    return {'result':'native-final-set-valid','execution_permit':False,'schedule_checked':False,
            'replaces_authorizes_overwrite':False,'count':len(chosen)}
