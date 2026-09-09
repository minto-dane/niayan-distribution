# SPDX-License-Identifier: MIT
# Build a large tar stream without allocating the expanded contents.
import hashlib,io,json,lzma,pathlib,sys,tarfile
sys.path.insert(0,'/workspace/tests')
from make_deb_data_fixtures import CONTROL_TAR
from make_deb_control_fixtures import member
w=pathlib.Path('/results');out=io.BytesIO();compressed=lzma.LZMAFile(out,'w',preset=6)
class Sink:
 def __init__(self):self.size=0;self.hash=hashlib.sha256()
 def write(self,data):self.hash.update(data);self.size+=len(data);return compressed.write(data)
class Zeros:
 def read(self,n):return b'\0'*n
sink=Sink()
with tarfile.open(fileobj=sink,mode='w|',format=tarfile.USTAR_FORMAT) as archive:
 info=tarfile.TarInfo('./large.bin');info.size=96*1024*1024;info.mode=0o644;info.mtime=1788739200
 archive.addfile(info,Zeros())
compressed.close();encoded=out.getvalue();raw=b'!<arch>\n'+member('debian-binary',b'2.0\n')+member('control.tar',CONTROL_TAR)+member('data.tar.xz',encoded)
p=w/'original-media/large-xz.deb';p.write_bytes(raw)
(w/'large-input.json').write_text(json.dumps(dict(filename=p.name,synthetic=True,size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),encoded_sha256=hashlib.sha256(encoded).hexdigest(),expanded_sha256=sink.hash.hexdigest(),expanded_size=sink.size,payload_size=info.size),indent=2)+'\n')
print('large synthetic input:',len(raw),'expanded:',sink.size)
