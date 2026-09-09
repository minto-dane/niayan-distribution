import tarfile,io,subprocess,hashlib,json
from pathlib import Path
out=Path('/work/probes');out.mkdir(exist_ok=True)
def entry(name,kind=tarfile.REGTYPE,**kw):
 t=tarfile.TarInfo(name);t.type=kind;t.mode=0o755 if kind==tarfile.DIRTYPE else 0o6751;t.uid=123;t.gid=456;t.mtime=1700000000
 for k,v in kw.items():setattr(t,k,v)
 return t
core=[entry('.',tarfile.DIRTYPE),entry('usr',tarfile.DIRTYPE,mode=0o2755),entry('usr/file',size=3),entry('alias',tarfile.LNKTYPE,linkname='usr/file'),entry('sym',tarfile.SYMTYPE,linkname='/usr/file',mode=0o777),entry('char',tarfile.CHRTYPE,devmajor=1,devminor=3),entry('block',tarfile.BLKTYPE,devmajor=8,devminor=1),entry('fifo',tarfile.FIFOTYPE),entry('tmp',tarfile.DIRTYPE,mode=0o1777)]
cases={'core-ustar':(core,tarfile.USTAR_FORMAT),'positive-fraction':([entry('fraction',pax_headers={'mtime':'1700000000.25'})],tarfile.PAX_FORMAT),'positive-nine-digits':([entry('fraction',pax_headers={'mtime':'1700000000.250000000'})],tarfile.PAX_FORMAT),'negative-integer-pax':([entry('negative',pax_headers={'mtime':'-1'})],tarfile.PAX_FORMAT)}
results=[]
for name,(items,fmt) in cases.items():
 tar=out/(name+'.tar')
 with tarfile.open(tar,'w',format=fmt) as f:
  for t in items:f.addfile(t,io.BytesIO(b'abc') if t.size else None)
 images=[]
 for suffix,tz in [('a','UTC'),('b','Pacific/Honolulu')]:
  image=out/(name+'-'+suffix+'.erofs')
  cmd=['mkfs.erofs','--workers=1','--tar=f','-E','force-inode-extended','-b4096','-T1788739200','--mkfs-time','-U','cc580a36-7187-4494-838e-6c8d25bf917a','--preserve-mtime',str(image),str(tar)]
  import os
  p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env={**os.environ,'TZ':tz});(out/(name+'-'+suffix+'.mkfs.log')).write_bytes(p.stdout)
  r={'image':image.name,'command':cmd,'returncode':p.returncode,'TZ':tz}
  if p.returncode==0:
   r['sha256']=hashlib.sha256(image.read_bytes()).hexdigest()
   q=subprocess.run(['fsck.erofs','--extract',str(image)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
   r['fsck_returncode']=q.returncode;(out/(name+'-'+suffix+'.fsck.log')).write_bytes(q.stdout)
  images.append(r)
 results.append({'name':name,'tar_sha256':hashlib.sha256(tar.read_bytes()).hexdigest(),'images':images})
 print(name,images[0].get('sha256')==images[1].get('sha256'),flush=True)
(out/'extra-results.json').write_text(json.dumps(results,indent=2)+'\n')
