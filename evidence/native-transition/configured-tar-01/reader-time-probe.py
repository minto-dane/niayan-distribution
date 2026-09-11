# SPDX-License-Identifier: BSD-3-Clause
import ctypes as C,json
lib=C.CDLL('libarchive.so.13')
def fn(name,result,args):
 f=getattr(lib,name);f.restype=result;f.argtypes=args;return f
p=C.c_void_p;i=C.c_int;s=C.c_char_p
reader=fn('archive_read_new',p,[])()
assert fn('archive_read_support_format_tar',i,[p])(reader)==0
assert fn('archive_read_open_filename',i,[p,s,C.c_size_t])(reader,b'/evidence/export-03/normal.tar',65536)==0
e=p();assert fn('archive_read_next_header',i,[p,C.POINTER(p)])(reader,C.byref(e))==0
count=fn('archive_entry_xattr_reset',i,[p])(e);rows=[]
next_attr=fn('archive_entry_xattr_next',i,[p,C.POINTER(s),C.POINTER(p),C.POINTER(C.c_size_t)])
for _ in range(count):
 name=s();value=p();size=C.c_size_t();assert next_attr(e,C.byref(name),C.byref(value),C.byref(size))==0
 rows.append({'name_length':len(name.value),'name_hex':name.value.hex(),'value_hex':C.string_at(value,size.value).hex()})
times={}
for kind in ['mtime','atime','ctime','birthtime']:
 times[kind]={'present':bool(fn('archive_entry_'+kind+'_is_set',i,[p])(e)), 'seconds':fn('archive_entry_'+kind,C.c_long,[p])(e), 'nanoseconds':fn('archive_entry_'+kind+'_nsec',C.c_long,[p])(e)}
fn('archive_read_free',i,[p])(reader)
print(json.dumps({'xattrs':rows,'clocks':times},indent=2))
