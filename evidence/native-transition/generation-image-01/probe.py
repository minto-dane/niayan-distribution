import subprocess,json,hashlib
from pathlib import Path
out=Path('/work/probes');out.mkdir(exist_ok=True)
results=[]
for row in json.loads(Path('/fixtures/manifest.json').read_text()):
 if not row['accepted']:continue
 name=Path(row['filename']).stem
 raw=subprocess.check_output(['dpkg-deb','--fsys-tarfile','/fixtures/'+row['filename']])
 tar=out/(name+'.tar');tar.write_bytes(raw)
 image=out/(name+'.erofs')
 cmd=['mkfs.erofs','--workers=1','--tar=f','-E','force-inode-extended','-b4096','-T1788739200','--mkfs-time','-U','cc580a36-7187-4494-838e-6c8d25bf917a','--preserve-mtime',str(image),str(tar)]
 p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 (out/(name+'.mkfs.log')).write_bytes(p.stdout)
 result={'fixture':row,'command':cmd,'returncode':p.returncode,'tar_sha256':hashlib.sha256(raw).hexdigest()}
 if p.returncode==0:
  result['image_sha256']=hashlib.sha256(image.read_bytes()).hexdigest()
  q=subprocess.run(['fsck.erofs','--extract',str(image)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  (out/(name+'.fsck.log')).write_bytes(q.stdout);result['fsck_returncode']=q.returncode
  q=subprocess.run(['dump.erofs','--ls','--path=/',str(image)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  (out/(name+'.ls.log')).write_bytes(q.stdout)
 results.append(result)
 print(name,p.returncode,flush=True)
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
