# SPDX-License-Identifier: MIT
# Qualification only: read original DEBs; no package or script execution.
import hashlib,json,pathlib,re,subprocess,tempfile
root=pathlib.Path('/results'); media=pathlib.Path('/media'); binary='/workspace/build/test-bin/run_deb_metadata_tests'
report=[]
for row in json.loads((root/'original-media-inputs.json').read_text())['files']:
 source=media/row['filename']; raw=source.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
 assert digest==row['sha256'] and len(raw)==row['size']
 with tempfile.TemporaryDirectory(dir='/results/probe-cas') as d:
  run=subprocess.run([binary,d,str(media),source.name],capture_output=True,text=True,timeout=120)
  (root/(source.name+'.probe.log')).write_text(run.stdout+run.stderr); run.check_returncode()
  values={}; names=[]
  for line in run.stdout.splitlines():
   key,_,value=line.partition(' ')
   if key=='FIELD':names.append(value)
   elif key!='PASS':values[key]=value
  # dpkg-deb is a build-time independent oracle, not a production dependency or backend.
  fields={}
  for key in ['Package','Version','Architecture','Source','Multi-Arch','Essential','Protected','Installed-Size']:
   fields[key.lower()]=subprocess.check_output(['dpkg-deb','--field',str(source),key],text=True,timeout=30).strip()
  assert values['ORIGINAL']==digest
  assert values['PACKAGE']==fields['package'] and values['VERSION']==fields['version'] and values['ARCHITECTURE']==fields['architecture']
  source_name=fields['package']; source_version=fields['version']
  if fields['source']:
   m=re.fullmatch(r'([a-z0-9][a-z0-9+.-]+)(?:\s+\(([^()]+)\))?',fields['source']); assert m
   source_name=m[1]; source_version=m[2] or source_version
  assert values['SOURCE']==source_name+' '+source_version
  assert values['MULTI'].lower()==(fields['multi-arch'] or 'no')
  assert (values['ESSENTIAL']=='TRUE')==(fields['essential']=='yes')
  assert (values['PROTECTED']=='TRUE')==(fields['protected']=='yes')
  expected_size=('TRUE '+str(int(fields['installed-size']))) if fields['installed-size'] else 'FALSE 0'
  assert values['INSTALLED_SIZE']==expected_size
  control_hash=values['CONTROL']; cas=pathlib.Path(d)/'objects'/control_hash[:2]/control_hash[2:]; control=cas.read_bytes()
  assert hashlib.sha256(control).hexdigest()==control_hash
  expected_names=[line.split(b':',1)[0].decode('ascii').lower() for line in control.splitlines() if line and line[:1] not in (b' ',b'\t')]
  assert names==expected_names and len(names)==len(set(names))
  assert source.read_bytes()==raw
  report.append(dict(row,result='pass',metadata=values,field_names=names))
(root/'real-debs.json').write_text(json.dumps({'result':'pass','scope':'original DEB native field/identity observation compared with dpkg-deb read-only build oracle and raw CAS; no dependency/effect/installation qualification','files':report},indent=2)+'\n')
print('PASS original metadata observations:',len(report),'fields:',sum(len(x['field_names']) for x in report))
