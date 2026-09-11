# SPDX-License-Identifier: BSD-3-Clause
import ctypes as C, io, json, tarfile
from decimal import Decimal
from pathlib import Path
lib=C.CDLL('libarchive.so.13')
def fn(name,result,args):
 f=getattr(lib,name);f.restype=result;f.argtypes=args;return f
ptr=C.c_void_p; integer=C.c_int; text=C.c_char_p; wide=C.c_longlong
new=fn('archive_write_new',ptr,[]); writer=new()
error=fn('archive_error_string',text,[ptr])
def good(value):
 if value!=0:raise RuntimeError((value,error(writer)))
good(fn('archive_write_set_format_pax',integer,[ptr])(writer))
good(fn('archive_write_set_options',integer,[ptr,text])(writer,b'pax:hdrcharset=BINARY,pax:xattrheader=LIBARCHIVE'))
buffer=C.create_string_buffer(65536);used=C.c_size_t()
good(fn('archive_write_open_memory',integer,[ptr,ptr,C.c_size_t,C.POINTER(C.c_size_t)])(writer,buffer,len(buffer),C.byref(used)))
e=fn('archive_entry_new',ptr,[])()
fn('archive_entry_set_pathname',None,[ptr,text])(e,b'etc/raw-\xff.conf')
fn('archive_entry_set_mode',None,[ptr,C.c_uint])(e,0o106740)
fn('archive_entry_set_uid',None,[ptr,wide])(e,4294967294)
fn('archive_entry_set_gid',None,[ptr,wide])(e,1234)
fn('archive_entry_set_size',None,[ptr,wide])(e,3)
clocks={'mtime':(-42,123456789),'atime':(123,456),'ctime':(-1,1),'birthtime':(0,42)}
for kind,(seconds,nsec) in clocks.items():fn('archive_entry_set_'+kind,None,[ptr,C.c_long,C.c_long])(e,seconds,nsec)
add=fn('archive_entry_xattr_add_entry',None,[ptr,text,ptr,C.c_size_t])
for name,value in [(b'user.empty',b''),(b'user.binary',b'\x00\xff\x7f'),(b'user.raw-\xff',b'x')]:add(e,name,value,len(value))
fn('archive_entry_copy_fflags_text',text,[ptr,text])(e,b'nodump')
acl=fn('archive_entry_acl_add_entry',integer,[ptr,integer,integer,integer,integer,text])
# Public libarchive constants from archive_entry.h, numeric POSIX access ACL.
for perm,tag,who in [(7,10002,-1),(4,10001,42),(4,10004,-1),(4,10005,-1),(0,10006,-1)]:good(acl(e,256,perm,tag,who,None))
good(fn('archive_write_header',integer,[ptr,ptr])(writer,e))
assert fn('archive_write_data',C.c_ssize_t,[ptr,ptr,C.c_size_t])(writer,b'abc',3)==3
good(fn('archive_write_close',integer,[ptr])(writer))
fn('archive_write_free',integer,[ptr])(writer);fn('archive_entry_free',None,[ptr])(e)
raw=buffer.raw[:used.value];Path('/evidence/writer-libarchive.tar').write_bytes(raw)
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:',encoding='utf-8',errors='surrogateescape') as archive:
 item=archive.getmembers()[0]
 results={'libarchive':fn('archive_version_string',text,[])().decode(),'path_hex':item.name.encode('utf-8','surrogateescape').hex(),'mode':oct(item.mode),'uid':item.uid,'gid':item.gid,'pax':{k.encode('utf-8','surrogateescape').hex():v.encode('utf-8','surrogateescape').hex() for k,v in item.pax_headers.items()},'clocks':{}}
 for kind,(s,n) in clocks.items():
  key='LIBARCHIVE.creationtime' if kind=='birthtime' else kind
  got=item.pax_headers.get(key);want=Decimal(s)+Decimal(n)/Decimal(1000000000)
  results['clocks'][kind]={'encoded':got,'expected':str(want),'match':got is not None and Decimal(got)==want}
print(json.dumps(results,indent=2))
