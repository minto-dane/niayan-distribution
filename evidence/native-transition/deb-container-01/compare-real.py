import hashlib,json,pathlib,subprocess,tempfile
root=pathlib.Path('/results'); media=pathlib.Path('/media'); binary='/workspace/build/test-bin/run_deb_container_tests'
inputs=json.loads((root/'original-media-inputs.json').read_text()); report=[]
for row in inputs['files']:
 source=media/row['filename']; raw=source.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
 assert digest==row['sha256'] and len(raw)==row['size']
 with tempfile.TemporaryDirectory(dir='/results/probe-cas') as d:
  run=subprocess.run([binary,d,str(media),source.name],capture_output=True,text=True,timeout=120,check=True)
  (root/(source.name+'.probe.log')).write_text(run.stdout+run.stderr)
  lines=run.stdout.splitlines(); original=next(x.split() for x in lines if x.startswith('ORIGINAL '))
  assert original[1:]==[digest,str(len(raw))]
  expected_names=subprocess.check_output(['ar','t',str(source)],text=True).splitlines()
  members=[]
  for line in lines:
   if not line.startswith('MEMBER '): continue
   _,name,member_digest,offset,size=line.split(); offset=int(offset); size=int(size)
   extracted=subprocess.check_output(['ar','p',str(source),name],timeout=30)
   assert extracted==raw[offset:offset+size] and len(extracted)==size
   assert hashlib.sha256(extracted).hexdigest()==member_digest
   assert (pathlib.Path(d)/'objects'/member_digest[:2]/member_digest[2:]).read_bytes()==extracted
   members.append({'name':name,'sha256':member_digest,'offset':offset,'size':size})
  assert [x['name'] for x in members]==expected_names
  assert (pathlib.Path(d)/'objects'/digest[:2]/digest[2:]).read_bytes()==raw
  assert source.read_bytes()==raw
  report.append(dict(row,members=members,result='pass'))
(root/'real-debs.json').write_text(json.dumps({'result':'pass','scope':'original ar envelopes and exact compressed CAS members; no tar semantics or installation','files':report},indent=2)+'\n')
print('PASS: original DEBs and all members independently matched with ar:',len(report))
