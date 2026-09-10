# SPDX-License-Identifier: MIT
"""Deterministic, synthetic benchmark inputs; requires a new private directory."""
import gzip,hashlib,io,json,sys,tarfile
from pathlib import Path
media=Path(sys.argv[1]);media.mkdir(mode=0o700)
def tar(entries):
 out=io.BytesIO()
 with tarfile.open(fileobj=out,mode='w',format=tarfile.USTAR_FORMAT) as tf:
  for name,data in entries:
   ti=tarfile.TarInfo(name);ti.size=len(data);ti.mode=0o644;ti.mtime=0;tf.addfile(ti,io.BytesIO(data))
 return gzip.compress(out.getvalue(),mtime=0)
def member(name,data):
 return (name+'/').ljust(16).encode()+b'0           0     0     100644  '+str(len(data)).ljust(10).encode()+b'`\n'+data+(b'\n' if len(data)%2 else b'')
for i in range(1,257):
 control=f'Package: shared-preflight-{i}\nVersion: 1\nArchitecture: all\nMaintainer: Test <test@example.invalid>\nDescription: synthetic scaling fixture\n'.encode()
 data=b'!<arch>\n'+member('debian-binary',b'2.0\n')+member('control.tar.gz',tar([('control',control)]))+member('data.tar.gz',tar([]))
 (media/f'package-{i}.deb').write_bytes(data)
for i in range(1,5):(media/f'shared-{i}').write_bytes(bytes([i])*2*1024*1024)
print(json.dumps({p.name:dict(size=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(media.iterdir())},indent=2))
