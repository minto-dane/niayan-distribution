import subprocess,tarfile,io,json,hashlib
from pathlib import Path
old=Path.cwd();reports={}
for option in ('--ctrl-tarfile','--fsys-tarfile'):
 values=[]
 for folder in ('build-a','build-b'):
  raw=subprocess.check_output(['dpkg-deb',option,str(old/folder/'niaos-root-preparation_0.3.0_amd64.deb')])
  with tarfile.open(fileobj=io.BytesIO(raw)) as t:
   values.append({m.name:dict(mode=m.mode,uid=m.uid,gid=m.gid,mtime=m.mtime,size=m.size,content=hashlib.sha256(t.extractfile(m).read()).hexdigest() if m.isfile() else None) for m in t})
 assert set(values[0])==set(values[1])
 reports[option]={n:[values[0][n],values[1][n]] for n in values[0] if values[0][n]!=values[1][n]}
print(json.dumps(dict(differences=reports),indent=2))
