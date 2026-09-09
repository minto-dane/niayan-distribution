"""Experimental image fidelity comparison, no extraction or installation."""
import hashlib,json,stat,tarfile,decimal
from pathlib import Path
from read_erofs import Image
base=Path(__file__).resolve().parent/'probes'
results=[]
for image in sorted(base.glob('*.erofs')):
 if image.stat().st_size==0:continue
 name=image.stem
 tar=base/((name[:-2] if name.endswith(('-a','-b')) else name)+'.tar')
 # Only successful construction outputs are candidates for readback.
 if name in ('basic','gnu-numeric'):continue
 observed=Image(image).tree();issues=[];checked=0;expected=set()
 with tarfile.open(tar,'r:') as f:
  members=f.getmembers();by_name={t.name.removeprefix('./').rstrip('/'):t for t in members}
  def canonical(n):return '' if n in ('.','./') else n.removeprefix('./').rstrip('/')
  for t in members:
   path=canonical(t.name);expected.add(path);checked+=1
   def difference(field,want,actual):
    if want!=actual:issues.append({'path':path,'field':field,'expected':want,'observed':actual})
   if path not in observed:issues.append({'path':path,'field':'missing'});continue
   o=observed[path];original=t
   if t.islnk():
    seen=set()
    while t.islnk():
     assert t.name not in seen;seen.add(t.name);t=by_name[canonical(t.linkname)]
    target=observed[canonical(t.name)]
    difference('hardlink inode',target['nid'],o['nid'])
   kind=stat.S_IFREG if t.isfile() else stat.S_IFDIR if t.isdir() else stat.S_IFLNK if t.issym() else stat.S_IFCHR if t.ischr() else stat.S_IFBLK if t.isblk() else stat.S_IFIFO if t.isfifo() else None
   assert kind is not None
   difference('mode',kind|(t.mode&0o7777),o['mode']);difference('uid',int(t.pax_headers.get('uid',t.uid)),o['uid']);difference('gid',int(t.pax_headers.get('gid',t.gid)),o['gid'])
   timestamp=decimal.Decimal(str(t.pax_headers.get('mtime',t.mtime)))
   seconds=int(timestamp.to_integral_value(rounding=decimal.ROUND_FLOOR));ns=int((timestamp-seconds)*1000000000)
   difference('mtime',[seconds,ns],[o['mtime'],o['mtime_nsec']])
   if t.isfile():
    h=hashlib.sha256();stream=f.extractfile(t)
    for block in iter(lambda:stream.read(65536),b''):h.update(block)
    difference('content',h.hexdigest(),o['sha256']);difference('size',t.size,o['size'])
   if t.issym():difference('symlink',t.linkname,o['link'])
   if t.ischr() or t.isblk():
    raw=o['block'];major=(raw>>8)&0xfff;minor=(raw&0xff)|((raw>>12)&0xfff00)
    difference('device',[t.devmajor,t.devminor],[major,minor])
   for key,value in t.pax_headers.items():
    if key.startswith('SCHILY.xattr.'):
     key=key.removeprefix('SCHILY.xattr.');difference('xattr:'+key,value.encode('utf8').hex(),o['xattrs'].get(key))
    elif key in ('SCHILY.acl.access','SCHILY.acl.default'):
     field='system.posix_acl_'+key.rsplit('.',1)[1]
     if field not in o['xattrs']:issues.append({'path':path,'field':field,'expected':value,'observed':None})
    elif key in ('SCHILY.fflags','atime','ctime','LIBARCHIVE.creationtime'):
     issues.append({'path':path,'field':key,'expected':value,'observed':'no separate on-disk field in tested profile'})
 record={'image':image.name,'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'tar_sha256':hashlib.sha256(tar.read_bytes()).hexdigest(),'checked_entries':checked,'issues':issues,'undeclared_directories':[{'path':p,'mode':observed[p]['mode']&0o7777,'uid':observed[p]['uid'],'gid':observed[p]['gid']} for p in sorted(set(observed)-expected)],'declared_fields_match':not issues}
 results.append(record)
 (base/(name+'.readback.json')).write_text(json.dumps(observed,ensure_ascii=False,indent=2)+'\n')
report={'qualification':'not-accepted-for-direct-payload-input','scope':'17 successful images, synthetic fixtures only; no kernel mount or boot acceptance','images':results}
(base/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
for r in results:print(r['image'],r['checked_entries'],'entries',len(r['issues']),'differences')
assert len(results)==17
assert all(not r['issues'] for r in results if r['image'].startswith('core-ustar-'))
assert any(i['field']=='system.posix_acl_access' for r in results for i in r['issues'])
assert sum(any(i['field']=='mtime' for i in r['issues']) for r in results)==4
print('Recorded differences independently confirmed; backend remains unaccepted.')
