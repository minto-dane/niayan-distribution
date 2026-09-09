# SPDX-License-Identifier: MIT
# Read-only qualification against the independent Python reference profile.
import collections,hashlib,json,pathlib,subprocess,sys
sys.path.insert(0,'/reference')
from debian_semantics import relations
w=pathlib.Path('/results');data=json.loads((w/'corpus-inputs.json').read_text())
ops={'':'ANY_VERSION','<<':'LESS_THAN','<=':'AT_MOST','=':'EXACTLY','>=':'AT_LEAST','>>':'GREATER_THAN'}
counts=collections.Counter();results=[];total=0
for row in data['cases']:
 field,value=row['field'],row['value'];groups=relations(value,provides=field=='provides',alternatives=field in {'depends','pre-depends','recommends','suggests'})
 expected=[]
 for i,group in enumerate(groups,1):
  for atom in group:expected.append([i,atom.name,'' if atom.architecture=='unqualified' else atom.architecture,ops[atom.operator],atom.version])
 run=subprocess.run(['/workspace/build/test-bin/run_deb_relations_tests',field,value],capture_output=True,text=True,timeout=30)
 assert run.returncode==0,(row,run.returncode,run.stderr)
 actual=[]
 for line in run.stdout.splitlines():
  g,name,arch,op,ver=line.split('|');actual.append([int(g),name,arch,op,ver])
 assert expected==actual,(row,expected,actual)
 counts[field]+=1;total+=len(actual)
 results.append(dict(package=row['package'],field=field,value_sha256=hashlib.sha256(value.encode()).hexdigest(),atoms=len(actual),parsed_sha256=hashlib.sha256(json.dumps(actual,separators=(',',':')).encode()).hexdigest()))
report=dict(result='pass',scope='Original ISO status relationship values only; Python single-native-profile lexical/group oracle; not original DEB supply, whole control validation, field semantics or installation qualification',status_sha256=data['status_sha256'],installed_count=data['installed_count'],relationship_fields=len(results),atoms=total,field_counts=dict(counts),reference_inputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [pathlib.Path('/reference/debian_semantics.py'),pathlib.Path('/reference/nia_common.py')]},cases=results)
(w/'corpus-results.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS ISO status corpus:',data['installed_count'],'packages,',len(results),'fields,',total,'atoms')
