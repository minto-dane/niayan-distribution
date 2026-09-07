#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded offline RPM-MD structural/byte checks for image assembly only.
No signature substitute, dependency solving, remote fetch, or RPM installation.
Reject external locations, XML entities and unsupported compression/algorithms.
"""
from __future__ import annotations
import bz2,gzip,hashlib,io,lzma,os,stat
from pathlib import PurePosixPath
from defusedxml import ElementTree as XML
from defusedxml.common import DefusedXmlException
from xml.etree.ElementTree import ParseError
MAX_COMPRESSED=32*1024*1024
MAX_PLAIN=128*1024*1024
RM='http://linux.duke.edu/metadata/repo'
PM='http://linux.duke.edu/metadata/common'
class InvalidMetadata(ValueError):pass

def safe_path(s):
 if not isinstance(s,str) or not s or len(s)>2048 or '\\' in s or ':' in s or any(ord(c)<33 or ord(c)>126 for c in s):raise InvalidMetadata('unsafe RPM-MD location')
 if PurePosixPath(s).is_absolute() or any(p in ('','.', '..') for p in s.split('/')):raise InvalidMetadata('escaping RPM-MD location')
 return s

def read(cache,rel,limit=MAX_COMPRESSED):
 safe_path(rel);d=os.open(cache,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
 try:
  parts=rel.split('/')
  for n in parts[:-1]:
   z=os.open(n,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=d);os.close(d);d=z
  f=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=d)
  try:
   a=os.fstat(f)
   if not stat.S_ISREG(a.st_mode) or a.st_size>limit:raise InvalidMetadata('non-regular/oversized metadata')
   out=bytearray()
   while len(out)<=limit:
    b=os.read(f,min(65536,limit+1-len(out)))
    if not b:break
    out.extend(b)
   z=os.fstat(f)
   if len(out)>limit or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns):raise InvalidMetadata('metadata changed during read')
   return bytes(out)
  finally:os.close(f)
 finally:os.close(d)

def unpack(name,data):
 if name.endswith('.gz'):
  with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:out=f.read(MAX_PLAIN+1)
 elif name.endswith('.xz'):
  dec=lzma.LZMADecompressor(memlimit=128*1024*1024);out=dec.decompress(data,max_length=MAX_PLAIN+1)
  if not dec.eof or dec.unused_data:raise InvalidMetadata('truncated/concatenated/oversized xz metadata')
 elif name.endswith('.bz2'):
  dec=bz2.BZ2Decompressor();out=dec.decompress(data,max_length=MAX_PLAIN+1)
  if not dec.eof or dec.unused_data:raise InvalidMetadata('truncated/concatenated/oversized bz2 metadata')
 elif name.endswith('.xml'):out=data
 else:raise InvalidMetadata('unsupported metadata compression (never silently ignored)')
 if len(out)>MAX_PLAIN:raise InvalidMetadata('decompressed metadata exceeds bound')
 return out

def xml(data):
 try:root=XML.fromstring(data,forbid_dtd=True,forbid_entities=True,forbid_external=True)
 except (DefusedXmlException,ParseError) as e:raise InvalidMetadata("unsafe/malformed XML") from e
 for e in root.iter():
  if '{http://www.w3.org/XML/1998/namespace}base' in e.attrib:raise InvalidMetadata('XML base indirection forbidden')
 return root

def only(parent,tag):
 items=parent.findall(tag)
 if len(items)!=1:raise InvalidMetadata('missing/duplicate required metadata element')
 return items[0]

def check_hash(item,data):
 alg=item.get('type');expected=item.text
 if alg not in ('sha256','sha512'):raise InvalidMetadata('weak/unsupported metadata hash')
 if not expected or hashlib.new(alg,data).hexdigest()!=expected:raise InvalidMetadata('metadata checksum mismatch')

def verify_repository(repo,cache):
 base=safe_path(repo['snapshot_path']);raw=read(cache,base+'/repodata/repomd.xml')
 if hashlib.sha256(raw).hexdigest()!=repo['repomd_sha256']:raise InvalidMetadata('repomd changed')
 root=xml(raw)
 if root.tag!='{'+RM+'}repomd':raise InvalidMetadata('wrong repomd namespace/root')
 records=root.findall('{'+RM+'}data')
 if not 1<=len(records)<=64:raise InvalidMetadata('metadata catalog bounds')
 primary=None;seen=set();paths=set()
 for row in records:
  kind=row.get('type')
  if not kind or kind in seen:raise InvalidMetadata('duplicate metadata kind')
  seen.add(kind);loc=only(row,'{'+RM+'}location')
  if set(loc.attrib)!={'href'}:raise InvalidMetadata('external metadata location')
  rel=safe_path(loc.get('href'));path=base+'/'+rel
  if path in paths:raise InvalidMetadata('metadata location alias')
  paths.add(path);body=read(cache,path);check_hash(only(row,'{'+RM+'}checksum'),body)
  size=row.findall('{'+RM+'}size')
  if len(size)>1 or (size and size[0].text!=str(len(body))):raise InvalidMetadata('metadata size mismatch')
  # Only primary XML needs interpretation here. Other metadata bytes must still
  # be pinned/checksummed; no claim that their application semantics are proven.
  if kind=='primary':
   plain=unpack(rel,body)
   oc=row.findall('{'+RM+'}open-checksum');osize=row.findall('{'+RM+'}open-size')
   if len(oc)>1 or len(osize)>1:raise InvalidMetadata('duplicate open metadata fields')
   if oc:check_hash(oc[0],plain)
   if osize and osize[0].text!=str(len(plain)):raise InvalidMetadata('open size mismatch')
   primary=xml(plain)
 if primary is None or primary.tag!='{'+PM+'}metadata':raise InvalidMetadata('missing primary RPM metadata')
 packages=primary.findall('{'+PM+'}package')
 if not 1<=len(packages)<=100000 or primary.get('packages')!=str(len(packages)):raise InvalidMetadata('package metadata count mismatch')
 result={}
 for row in packages:
  if row.get('type')!='rpm':raise InvalidMetadata('non-RPM catalog entry')
  loc=only(row,'{'+PM+'}location')
  if set(loc.attrib)!={'href'}:raise InvalidMetadata('external package location')
  path=base+'/'+safe_path(loc.get('href'))
  if path in result or not path.endswith('.rpm'):raise InvalidMetadata('duplicate/invalid RPM path')
  ver=only(row,'{'+PM+'}version');cs=only(row,'{'+PM+'}checksum')
  if cs.get('type')!='sha256':raise InvalidMetadata('package checksum must be SHA-256 for this profile')
  result[path]={'name':only(row,'{'+PM+'}name').text,'arch':only(row,'{'+PM+'}arch').text,
      'epoch':ver.get('epoch'),'version':ver.get('ver'),'release':ver.get('rel'),'sha256':cs.text}
 return result
