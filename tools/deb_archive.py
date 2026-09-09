# SPDX-License-Identifier: MIT
"""Read a bounded DEB without installing, executing, or extracting to the host.

Observations are content-bound, not signed execution grants. This is an offline
Python qualification tool, NOT a proven parser or a privileged installer.
"""
from __future__ import annotations
import io,lzma,re,tarfile,zlib
from pathlib import PurePosixPath
from nia_common import Invalid,sha,relative,read_file
from debian_semantics import NAME,split_version,relations
from debian_triggers import describe as describe_triggers

MAX_DEB=512*1024*1024
MAX_CONTROL=16*1024*1024
MAX_DATA=512*1024*1024
MAX_MEMBERS=131072
MAX_MEMBER=256*1024*1024
HOOKS={'preinst','postinst','prerm','postrm','config','triggers'}
DESCRIPTIVE={'package','version','architecture','source','maintainer','description','section','priority','homepage','bugs','origin','tag','installed-size','essential','protected','multi-arch','package-type','depends','pre-depends','recommends','suggests','enhances','breaks','conflicts','replaces','provides','built-using','static-built-using','built-for-profiles','auto-built-package','build-ids'}

def deb822(raw:bytes, *, limit=MAX_CONTROL, max_stanzas=262144)->list[dict[str,str]]:
    if len(raw)>limit:raise Invalid('control text size limit')
    try:text=raw.decode('utf-8')
    except UnicodeError as exc:raise Invalid('control is not UTF-8') from exc
    text=text.replace('\r\n','\n')
    if '\r' in text or any(ord(c)<32 and c not in '\n\t' for c in text):raise Invalid('control character')
    result=[];record={};last=None
    for line in text.split('\n'):
        if len(line)>65536:raise Invalid('control line too long')
        if not line:
            if record:
                result.append(record);record={};last=None
                if len(result)>max_stanzas:raise Invalid('too many stanzas')
            continue
        if line[0] in ' \t':
            if last is None:raise Invalid('orphan continuation')
            record[last]+='\n'+line[1:]
            if len(record[last])>MAX_CONTROL:raise Invalid('field too long')
            continue
        if ':' not in line:raise Invalid('missing control delimiter')
        key,value=line.split(':',1);key=key.lower()
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',key) or key in record:raise Invalid('invalid or duplicate control field')
        if len(record)>1024:raise Invalid('too many fields')
        record[key]=value.lstrip(' \t');last=key
    if record:result.append(record)
    if len(result)>max_stanzas:raise Invalid('too many stanzas')
    return result

def unfold(value:str)->str:
    return ' '.join(value.splitlines())

def ar_members(raw:bytes)->list[tuple[str,bytes]]:
    if len(raw)>MAX_DEB or not raw.startswith(b'!<arch>\n'):raise Invalid('invalid or oversized ar')
    pos=8;result=[];seen=set()
    while pos<len(raw):
        if len(result)>=16 or len(raw)-pos<60:raise Invalid('invalid ar header count/length')
        h=raw[pos:pos+60];pos+=60
        if h[-2:]!=b'`\n':raise Invalid('ar header trailer')
        try:
            name=h[:16].decode('ascii').rstrip(' ')
            if name.endswith('/'):name=name[:-1]
            ntext=h[48:58].decode('ascii').strip()
            if not re.fullmatch('[0-9]+',ntext):raise Invalid('ar size syntax')
            size=int(ntext)
            for off,end,base in ((16,28,10),(28,34,10),(34,40,10),(40,48,8)):
                token=h[off:end].decode('ascii').strip()
                if not token or any(c not in ('01234567' if base==8 else '0123456789') for c in token):raise Invalid('ar numeric metadata')
        except UnicodeError as exc:raise Invalid('ar non-ASCII header') from exc
        if not name or '/' in name or name in seen or size>len(raw)-pos:raise Invalid('ar duplicate/name/size')
        seen.add(name);result.append((name,raw[pos:pos+size]));pos+=size
        if size%2:
            if raw[pos:pos+1]!=b'\n':raise Invalid('ar padding')
            pos+=1
    if len(result)!=3 or result[0]!=( 'debian-binary', b'2.0\n'):
        raise Invalid('only canonical deb 2.0 with three members is qualified')
    if result[1][0] not in ('control.tar','control.tar.gz','control.tar.xz','control.tar.zst') or result[2][0] not in ('data.tar','data.tar.gz','data.tar.xz','data.tar.zst'):
        raise Invalid('unsupported DEB member/compression')
    return result

def decompress(name:str,raw:bytes,limit:int)->bytes:
    if name.endswith('.gz'):
        decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
    elif name.endswith('.xz'):
        decoder=lzma.LZMADecompressor(format=lzma.FORMAT_XZ,memlimit=128*1024*1024)
    elif name.endswith('.zst'):
        from zstd_bounded import decode
        return decode(raw,limit)
    elif name.endswith('.tar'):
        if len(raw)>limit:raise Invalid('tar size limit')
        return raw
    else:raise Invalid('unknown compression')
    try:
        if name.endswith('.gz'):
            out=decoder.decompress(raw,limit+1)
            if len(out)>limit or decoder.unconsumed_tail:raise Invalid('decompression output limit')
        else:out=decoder.decompress(raw,max_length=limit+1)
        if len(out)>limit or not decoder.eof or decoder.unused_data:raise Invalid('truncated, concatenated, or oversized compressed member')
        return out
    except (lzma.LZMAError,zlib.error,EOFError) as exc:raise Invalid('compressed member invalid') from exc

def member_path(name:str, *, directory=False)->str:
    if name in ('.','./'):
        if directory:return ''
        raise Invalid('root member is not a directory')
    if name.startswith('./'):name=name[2:]
    if directory:name=name.rstrip('/')
    return relative(name)

def tar_inventory(raw:bytes, *, control=False)->tuple[list[dict],dict[str,bytes]]:
    records=[];bodies={};seen=set();total=0
    if len(raw)%512 or len(raw)<1024:raise Invalid('tar block alignment')
    try:
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:',errorlevel=2) as tf:
            for member in tf:
                if len(records)>=MAX_MEMBERS:raise Invalid('tar member count limit')
                name=member_path(member.name,directory=member.isdir())
                if name in seen:raise Invalid('duplicate normalized tar path')
                seen.add(name)
                if name=='':continue
                if member.size<0 or member.size>MAX_MEMBER or member.uid<0 or member.gid<0 or member.uid>=2**32 or member.gid>=2**32:raise Invalid('tar metadata limit')
                if member.mode<0 or member.mode>0o7777:raise Invalid('tar mode outside supported mask')
                if type(member.mtime) not in (int,float) or member.mtime<0 or member.mtime>=2**63:
                    raise Invalid('unsupported tar timestamp')
                # Fractional mtime requires an exact-decimal adapter; never round silently.
                if member.mtime!=int(member.mtime):raise Invalid('fractional mtime not qualified')
                if member.sparse is not None:raise Invalid('sparse tar member not qualified')
                if control and not member.isfile():raise Invalid('control member must be a regular file')
                if member.isfile():kind='regular'
                elif member.isdir():kind='directory'
                elif member.issym():kind='symlink'
                elif member.islnk():kind='hardlink'
                else:raise Invalid('device/fifo/unknown tar type forbidden')
                pax={}
                for key,value in member.pax_headers.items():
                    if key in ('path','linkpath','size','mtime','uid','gid','uname','gname'):continue
                    if not key.startswith('SCHILY.xattr.'):raise Invalid('unmodeled pax extension')
                    if len(key)>512 or len(value)>65536:raise Invalid('xattr limit')
                    pax[key[len('SCHILY.xattr.'):]]=value
                link=''
                if kind=='symlink':
                    link=member.linkname
                    if not link or '\x00' in link or '\\' in link or any(ord(c)<32 for c in link):raise Invalid('invalid link')
                    # Lexical resolution only. Never dereference on the host.
                    parts=[] if link.startswith('/') else name.split('/')[:-1]
                    for part in link.split('/'):
                        if part in ('','.'):continue
                        if part=='..':
                            if not parts:raise Invalid('link escapes installation root')
                            parts.pop()
                        else:parts.append(part)
                elif kind=='hardlink':link=member_path(member.linkname)
                data=b''
                if kind=='regular':
                    stream=tf.extractfile(member)
                    if stream is None:raise Invalid('missing file payload')
                    data=stream.read(MAX_MEMBER+1)
                    if len(data)!=member.size:raise Invalid('payload size mismatch')
                    total+=len(data)
                    if total>(MAX_CONTROL if control else MAX_DATA):raise Invalid('unpacked byte limit')
                    if control:bodies[name]=data
                records.append({'path':name,'kind':kind,'mode':member.mode,'uid':member.uid,'gid':member.gid,
                    'size':member.size,'mtime':int(member.mtime),'sha256':sha(data) if kind=='regular' else None,
                    'link':link,'xattrs':pax})
            # tarfile stops at first terminator. Reject hidden nonzero tail.
            if len(raw)-tf.offset<1024 or any(raw[tf.offset:]):raise Invalid('missing tar terminator or hidden trailing data')
    except (tarfile.TarError,UnicodeError,ValueError) as exc:
        if isinstance(exc,Invalid):raise
        raise Invalid('malformed tar') from exc
    byname={x['path']:x for x in records}
    for entry in records:
        bits=entry['path'].split('/')
        for n in range(1,len(bits)):
            parent='/'.join(bits[:n])
            if parent in byname and byname[parent]['kind']!='directory':raise Invalid('non-directory archive ancestor')
        if entry['kind']=='hardlink':
            target=entry['link'];vis={entry['path']}
            for _ in range(64):
                if target in vis or target not in byname:raise Invalid('hardlink cycle or missing target')
                vis.add(target);other=byname[target]
                if other['kind']=='regular':
                    entry['resolved_sha256']=other['sha256'];break
                if other['kind']!='hardlink':raise Invalid('hardlink to non-file')
                target=other['link']
            else:raise Invalid('hardlink depth limit')
    return sorted(records,key=lambda x:x['path']),bodies

def inspect_bytes(raw:bytes)->dict:
    archive=ar_members(raw)
    control,files=tar_inventory(decompress(*archive[1],MAX_CONTROL),control=True)
    data,_=tar_inventory(decompress(*archive[2],MAX_DATA))
    if 'control' not in files:raise Invalid('missing control')
    stanzas=deb822(files['control'])
    if len(stanzas)!=1:raise Invalid('binary control must have one stanza')
    info=stanzas[0]
    for key in ('package','version','architecture'):
        if key not in info:raise Invalid('missing '+key)
    if not NAME.fullmatch(info['package']):raise Invalid('invalid package name')
    split_version(info['version'])
    if info['architecture'] not in ('amd64','all'):raise Invalid('architecture not qualified by this product')
    if info.get('package-type','deb')!='deb':raise Invalid('not a binary deb package')
    if info.get('multi-arch','no') not in ('no','same','foreign','allowed'):raise Invalid('unknown Multi-Arch')
    if info['architecture']=='all' and info.get('multi-arch')=='same':raise Invalid('Architecture all with Multi-Arch same')
    for key in ('essential','protected'):
        if info.get(key,'no') not in ('yes','no'):raise Invalid('invalid '+key)
    native={}
    for key in ('depends','pre-depends','recommends','suggests','enhances','breaks','conflicts','replaces','provides','built-using','static-built-using'):
        value=unfold(info.get(key,''))
        groups=relations(value,provides=key=='provides',alternatives=key not in ('breaks','conflicts','replaces','provides','built-using','static-built-using'))
        if key in ('built-using','static-built-using') and any(a.operator!='=' for g in groups for a in g):raise Invalid('source-use relation requires equality')
        native[key]=[[a.__dict__ for a in g] for g in groups]
    conf=[];paths={x['path'] for x in data}
    if 'conffiles' in files:
        try:lines=files['conffiles'].decode('utf-8').splitlines()
        except UnicodeError as exc:raise Invalid('conffiles encoding') from exc
        for line in lines:
            if not line:continue
            flags=[]
            if line.startswith('remove-on-upgrade '):flags=['remove-on-upgrade'];line=line[len('remove-on-upgrade '):]
            if not line.startswith('/'):raise Invalid('conffile must be absolute')
            path=relative(line[1:])
            if any(x['path']==path for x in conf):raise Invalid('duplicate conffile')
            if not flags and path not in paths:raise Invalid('conffile missing from data archive')
            conf.append({'path':path,'flags':flags})
    effects=[{'member':key,'sha256':sha(value)} for key,value in sorted(files.items()) if key in HOOKS]
    known_control={'control','conffiles','md5sums','shlibs','symbols','templates'}|HOOKS
    unknown_controls=sorted(set(files)-known_control)
    return {'schema':'org.niaos.deb-observation/v1','execution_permit':False,'archive_authenticated':False,
            'artifact_sha256':sha(raw),'format':'deb','identity':{k:info[k] for k in ('package','version','architecture')},
            'raw_control_sha256':sha(files['control']),'fields':info,'relationships':native,
            'control_inventory':control,'file_inventory':data,'conffiles':conf,'effect_members':effects,
            'trigger_declarations':describe_triggers(files.get('triggers',b'')),
            'unknown_control_members':unknown_controls,'unmodeled_fields':sorted(set(info)-DESCRIPTIVE),
            'runtime_dependencies_preserved':True,'maintainer_scripts_executed':False,
            'needs_reviewed_effect_contract':True,'native_database_created':False}

def inspect_file(path)->dict:
    return inspect_bytes(read_file(path,MAX_DEB))
