# SPDX-License-Identifier: MIT
# Independent ar hashes and dpkg-deb read-only data-stream oracle; no extraction.
import hashlib,json,pathlib,subprocess,tempfile
w=pathlib.Path('/results');media=w/'original-media';results=[]
inputs=json.loads((w/'original-media-inputs.json').read_text())['files']+[json.loads((w/'large-input.json').read_text())]
for row in inputs:
 source=media/row['filename'];raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==row['sha256'] and len(raw)==row['size']
 assert raw[:8]==b'!<arch>\n';offset=8;data=None
 while offset<len(raw):
  header=raw[offset:offset+60];assert len(header)==60 and header[-2:]==b'`\n';size=int(header[48:58]);name=header[:16].decode().rstrip().rstrip('/');offset+=60
  if name.startswith('data.tar'):data=raw[offset:offset+size]
  offset+=size+(size%2)
 assert data is not None and offset==len(raw)
 with tempfile.TemporaryDirectory(dir=w/'probe-cas') as cas:
  probe=w/(source.name+'.probe.log')
  run=subprocess.run(['python3','/results/probe-resources.py',str(probe),'/workspace/build/test-bin/run_deb_data_stream_tests',cas,str(media),source.name],capture_output=True,text=True,timeout=330)
  assert run.returncode==0,(source.name,run.stderr,probe.read_text());resources=json.loads(run.stdout)
  values={}
  for line in probe.read_text().splitlines():
   key,_,value=line.partition(' ')
   if key!='PASS':values[key]=value.strip()
  assert values['ORIGINAL']==row['sha256'];assert values['COMPRESSED']==hashlib.sha256(data).hexdigest();assert int(values['ENCODED_SIZE'])==len(data)
  # Build-time oracle only, writing stdout bytes into a hash rather than extracting.
  with tempfile.TemporaryFile() as err:
   proc=subprocess.Popen(['dpkg-deb','--fsys-tarfile',str(source)],stdout=subprocess.PIPE,stderr=err)
   digest=hashlib.sha256();size=0
   while block:=proc.stdout.read(65536):digest.update(block);size+=len(block)
   assert proc.wait(timeout=30)==0
  assert values['EXPANDED']==digest.hexdigest() and int(values['EXPANDED_SIZE'])==size
  path=pathlib.Path(cas)/'objects'/values['EXPANDED'][:2]/values['EXPANDED'][2:];stored=hashlib.sha256();stored_size=0
  with path.open('rb') as f:
   while block:=f.read(65536):stored.update(block);stored_size+=len(block)
  assert stored.hexdigest()==digest.hexdigest() and stored_size==size
  if row.get('synthetic'):
   assert size==row['expanded_size'] and digest.hexdigest()==row['expanded_sha256']
   # A measured stream-path check, not a memory proof for every format/package.
   assert resources['peak_child_rss_kib']*1024<size
  assert source.read_bytes()==raw
  results.append(dict(input=row,observation=values,resources=resources,result='pass'))
(w/'real-debs.json').write_text(json.dumps(dict(result='pass',scope='Data stream only; native versus read-only dpkg-deb and independent ar/CAS; 13 cached originals plus one synthetic large input; no tar ownership/effect qualification',files=results),indent=2)+'\n')
print('PASS data streams:',len(results),'expanded bytes:',sum(int(r['observation']['EXPANDED_SIZE']) for r in results),'max native KiB:',max(r['resources']['peak_child_rss_kib'] for r in results))
