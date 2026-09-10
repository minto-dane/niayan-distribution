# SPDX-License-Identifier: MIT
from collections import Counter
import hashlib,json,os,re,subprocess
from pathlib import Path
w=Path(__file__).resolve().parent;rows=[]
for label in ['baseline','candidate']:
 cas=w/('trace-'+label);cas.mkdir(mode=0o700);trace=w/(label+'-reads.trace')
 args=['python3','-B',str(w/'run-chaos-container.py'),'env','LD_LIBRARY_PATH=/evidence/injection/lib','/evidence/injection/strace','-qq','-y','-s','120','-e','trace=write,pread64','-o','/evidence/'+trace.name,'/workspace/pkgcore/build/bench-bin/run_shared_preflight_benchmark','/evidence/'+cas.name,'/evidence/media','16']
 with (w/(label+'-traced.log')).open('w') as log:subprocess.run(args,env={**os.environ,'PROBE_TREE':label},stdout=log,stderr=subprocess.STDOUT,check=True,timeout=650)
 text=(w/(label+'-traced.log')).read_text();shared=re.findall(r'BENCH_SHARED ([0-9a-f]{64})',text);assert len(shared)==4
 phases={i:Counter() for i in [1,2,3]};phase=None
 for line in trace.read_text().splitlines():
  marker=re.search(r'BENCH_PHASE ([123]) (BEGIN|END)',line)
  if marker:phase=int(marker[1]) if marker[2]=='BEGIN' else None
  if phase is None:continue
  m=re.search(r'^pread64\(\d+<[^>]+/objects/([0-9a-f]{2})/([0-9a-f]{62})>.*\) = (\d+)$',line)
  if m and m[1]+m[2] in shared:phases[phase][m[1]+m[2]]+=int(m[3])
 for phase,counts in phases.items():
  expected=(48 if phase in [1,2] else 16) if label=='baseline' else (17 if phase in [1,2] else 1)
  assert dict(counts)=={h:expected*2*1024*1024 for h in shared},(label,phase,dict(counts),expected)
 rows.append(dict(label=label,packages=16,shared_object_bytes=2*1024*1024,phase_read_bytes={str(k):dict(v) for k,v in phases.items()},trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest()))
 print('PASS exact shared read bytes',label,flush=True)
(w/'read-comparison.json').write_text(json.dumps(dict(result='pass',rows=rows,scope='actual shared CAS bytes read in marked phases; tracing capabilities are private lab only; no cached trust'),indent=2)+'\n')
