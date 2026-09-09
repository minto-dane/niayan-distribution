"""Read-only, uncompressed EROFS probe. Format: upstream erofs_fs.h v1.8.6."""
import struct,stat,json,hashlib,mmap,sys
class Image:
 def __init__(self,path):
  self.file=open(path,'rb');self.raw=mmap.mmap(self.file.fileno(),0,access=mmap.ACCESS_READ)
  assert self.u('I',1024)==0xe0f5e1e2
  self.bs=1<<self.u('B',1036);self.meta=self.u('I',1064)*self.bs;self.xbase=self.u('I',1068)*self.bs
  self.root=self.u('H',1038);assert self.bs==4096
  assert self.u('I',1104)&~1==0
 def u(self,fmt,offset):return struct.unpack_from('<'+fmt,self.raw,offset)[0]
 def read(self,offset,size):
  assert 0<=offset<=len(self.raw) and 0<=size<=len(self.raw)-offset
  return self.raw[offset:offset+size]
 def inode(self,nid):
  off=self.meta+nid*32;fmt=self.u('H',off);assert fmt&1
  count=self.u('H',off+2);xs=12+(count-1)*4 if count else 0
  mode=self.u('H',off+4)
  return dict(nid=nid,offset=off,layout=(fmt>>1)&7,mode=mode,size=self.u('Q',off+8),block=self.u('I',off+16),uid=self.u('I',off+24),gid=self.u('I',off+28),mtime=self.u('q',off+32),mtime_nsec=self.u('I',off+40),nlink=self.u('I',off+44),xattr_size=xs,xattrs=self.attrs(off+64,xs))
 def attrs(self,off,size):
  if not size:return {}
  out={};shared=self.u('B',off+4)
  def one(pos):
   nl,index,vl=struct.unpack_from('<BBH',self.raw,pos)
   prefixes={1:b'user.',2:b'system.posix_acl_access',3:b'system.posix_acl_default',4:b'trusted.',5:b'lustre.',6:b'security.'}
   assert index in prefixes
   key=(prefixes[index]+self.read(pos+4,nl)).decode('utf8');assert key not in out
   out[key]=self.read(pos+4+nl,vl).hex()
   return (4+nl+vl+3)//4*4
  for i in range(shared):one(self.xbase+self.u('I',off+12+4*i)*4)
  pos=off+12+4*shared
  while pos<off+size:pos+=one(pos)
  assert pos==off+size
  return out
 def data(self,item):
  size=item['size'];layout=item['layout'];assert layout in (0,2)
  full=size//self.bs*self.bs if layout==2 else size
  pos=item['block']*self.bs
  for start in range(0,full,65536):yield self.read(pos+start,min(65536,full-start))
  if full<size:yield self.read(item['offset']+64+item['xattr_size'],size-full)
 def tree(self):
  out={};pending=[('',self.root)];seen_dirs=set()
  while pending:
   name,nid=pending.pop();assert name not in out and len(out)<131072
   it=self.inode(nid);out[name]=it
   if stat.S_ISDIR(it['mode']):
    assert nid not in seen_dirs;seen_dirs.add(nid)
    data=b''.join(self.data(it))
    for start in range(0,len(data),self.bs):
     block=data[start:start+self.bs];first=struct.unpack_from('<H',block,8)[0];assert first%12==0
     offsets=[struct.unpack_from('<H',block,i+8)[0] for i in range(0,first,12)]+[len(block)]
     for i in range(first//12):
      child=block[offsets[i]:offsets[i+1]].rstrip(b'\0').decode('utf8')
      if child in ('.','..'):continue
      assert child and '/' not in child
      pending.append((name+'/'+child if name else child,struct.unpack_from('<Q',block,i*12)[0]))
   elif stat.S_ISREG(it['mode']) or stat.S_ISLNK(it['mode']):
    h=hashlib.sha256()
    for block in self.data(it):h.update(block)
    it['sha256']=h.hexdigest()
    if stat.S_ISLNK(it['mode']):it['link']=b''.join(self.data(it)).decode('utf8')
  return dict(sorted(out.items()))
if __name__=='__main__':print(json.dumps(Image(sys.argv[1]).tree(),ensure_ascii=False,indent=2))
