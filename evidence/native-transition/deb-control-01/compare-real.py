# SPDX-License-Identifier: MIT
# Private qualification probe; no installation or script execution.
import hashlib,io,json,pathlib,subprocess,tarfile,tempfile
root=pathlib.Path('/results'); media=pathlib.Path('/media'); binary='/workspace/build/test-bin/run_deb_control_tests'
inputs=json.loads((root/'original-media-inputs.json').read_text()); report=[]
for row in inputs['files']:
 source=media/row['filename']; raw=source.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
 assert digest==row['sha256'] and len(raw)==row['size']
 with tempfile.TemporaryDirectory(dir='/results/probe-cas') as d:
  run=subprocess.run([binary,d,str(media),source.name],capture_output=True,text=True,timeout=120)
  (root/(source.name+'.probe.log')).write_text(run.stdout+run.stderr)
  run.check_returncode()
  lines=run.stdout.splitlines(); original=next(x.split()[1] for x in lines if x.startswith('ORIGINAL '))
  archive_hash=next(x.split()[1] for x in lines if x.startswith('ARCHIVE ')); assert original==digest
  ar_names=subprocess.check_output(['ar','t',str(source)],text=True).splitlines()
  names=[n for n in ar_names if n.startswith('control.tar')]; assert len(names)==1
  encoded=subprocess.check_output(['ar','p',str(source),names[0]],timeout=30)
  assert hashlib.sha256(encoded).hexdigest()==archive_hash
  cas=lambda h:pathlib.Path(d)/'objects'/h[:2]/h[2:]
  assert cas(digest).read_bytes()==raw and cas(archive_hash).read_bytes()==encoded
  if names[0].endswith('.zst'):
   encoded=subprocess.run(['zstd','-d','--stdout'],input=encoded,capture_output=True,check=True,timeout=30).stdout
  with tarfile.open(fileobj=io.BytesIO(encoded),mode='r:*') as tar:
   expected=[]
   for item in tar:
    name='.' if item.name in ('.','./') else item.name.removeprefix('./')
    if item.isdir(): kind='DIRECTORY'; content='0'*64; size=0
    else:
     assert item.isreg(); kind='REGULAR'; body=tar.extractfile(item).read(); size=len(body); content=hashlib.sha256(body).hexdigest()
     assert cas(content).read_bytes()==body
    expected.append({'name':name,'kind':kind,'sha256':content,'size':size,'mode':item.mode,'uid':item.uid,'gid':item.gid,'mtime':int(item.mtime)})
  observed=[]
  for line in lines:
   if not line.startswith('ENTRY '):continue
   _,name,kind,content,size,mode,uid,gid,mtime=line.split()
   observed.append(dict(name=name,kind=kind,sha256=content,size=int(size),mode=int(mode),uid=int(uid),gid=int(gid),mtime=int(mtime)))
  assert observed==expected,source.name
  assert source.read_bytes()==raw
  report.append(dict(row,archive_sha256=archive_hash,entries=observed,result='pass'))
(root/'real-debs.json').write_text(json.dumps({'result':'pass','scope':'original control files and metadata with independent ar/Python tar parsing and CAS readback; no interpretation, installation or supply authentication','files':report},indent=2)+'\n')
print('PASS: original DEBs',len(report),'control entries',sum(len(x['entries']) for x in report))
