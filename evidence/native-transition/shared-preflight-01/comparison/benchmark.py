# SPDX-License-Identifier: MIT
import hashlib,json,os,re,subprocess
from pathlib import Path
w=Path(__file__).resolve().parent;reports=[]
for label in ['baseline','candidate']:
 env={**os.environ,'PROBE_TREE':label}
 command=['python3','-B',str(w/'run-container.py')]
 with (w/(label+'-benchmark-build.log')).open('w') as log:
  subprocess.run(command+['sh','-ec','cd /workspace/pkgcore; gprbuild -s -j1 -p -P bench.gpr'],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
 for count in [1,16,64]:
  tag=label+'-'+str(count);cas=w/('run-'+tag);cas.mkdir(mode=0o700)
  with (w/(tag+'.log')).open('w') as log:
   subprocess.run(command+['/workspace/pkgcore/build/bench-bin/run_shared_preflight_benchmark','/evidence/'+cas.name,'/evidence/media',str(count)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=650)
  raw=(w/(tag+'.log')).read_bytes();text=raw.decode()
  phases={int(k):int(v) for k,v in re.findall(r'BENCH_PHASE (\d+) END (\d+)',text)};assert set(phases)=={1,2,3}
  objects={k:v for k,v in re.findall(r'BENCH_(MAP|CATALOG|CLOSURE) ([0-9a-f]{64})',text)};assert len(objects)==3
  reports.append(dict(label=label,packages=count,phase_ms=phases,objects=objects,log_sha256=hashlib.sha256(raw).hexdigest()))
  (w/'benchmark.json').write_text(json.dumps(dict(status='running',rows=reports),indent=2)+'\n')
  print(tag,phases,flush=True)
for count in [1,16,64]:
 rows=[r for r in reports if r['packages']==count];assert rows[0]['objects']==rows[1]['objects']
(w/'benchmark.json').write_text(json.dumps(dict(status='pass',rows=reports,scope='one sample per point, hot local cache, 4x2MiB shared inputs and tiny native DEBs; not production throughput or a statistical latency estimate'),indent=2)+'\n')
