import json,subprocess,sys
from pathlib import Path
base=Path('/evidence');name=sys.argv[1];media=Path(sys.argv[2]);dest=base/name;dest.mkdir(mode=0o700)
p=subprocess.run(['python3','/evidence/probe-all.py',name,str(media)])
if p.returncode:raise SystemExit(p.returncode)
for direction in ['forward','reverse']:
 cas=base/(name+'-'+direction+'.cas');cas.mkdir(mode=0o700)
 listing=base/(name+'-'+direction+'.txt')
 paths=sorted(p.name for p in media.glob('*.deb'));listing.write_text(''.join(n+'\n' for n in (paths if direction=='forward' else paths[::-1])))
 log=base/(name+'-'+direction+'.log')
 result=subprocess.run(['python3','/evidence/probe-resources.py',str(log),'/workspace/build/test-bin/run_payload_index_tests',str(cas),str(media),str(listing),'--scan'],capture_output=True,text=True)
 (base/(name+'-'+direction+'-resources.json')).write_text(result.stdout)
 print(name,direction,result.stdout,flush=True)
 if result.returncode:raise SystemExit(result.returncode)
 subprocess.run(['python3','/workspace/tests/compare_payload_index.py','--media',str(media),'--probes',str(dest),'--index-log',str(log),'--output',str(base/(name+'-'+direction+'-oracle.json'))],check=True)
