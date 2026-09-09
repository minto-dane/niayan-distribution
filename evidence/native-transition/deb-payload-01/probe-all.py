import json, os, subprocess, sys
from pathlib import Path
root=Path('/evidence'); name=sys.argv[1] if len(sys.argv)>1 else 'debug-original'; dest=root/name; dest.mkdir(exist_ok=True,mode=0o700)
media=Path(sys.argv[2]) if len(sys.argv)>2 else Path('/originals')
accepted = {r['filename'] for r in json.loads((media/'manifest.json').read_text()) if r['accepted']} if (media/'manifest.json').exists() else None
results=[]
for p in sorted(media.glob('*.deb')):
 if accepted is not None and p.name not in accepted: continue
 cas=dest/(p.name+'.cas');cas.mkdir(mode=0o700,exist_ok=True)
 run=subprocess.run(['python3','/evidence/probe-resources.py',str(dest/(p.name+'.log')),'/workspace/build/test-bin/run_deb_payload_tests',str(cas),str(media),p.name],capture_output=True,text=True)
 result=json.loads(run.stdout); result['filename']=p.name;results.append(result)
 print(p.name, result, flush=True)
(dest/'resources.json').write_text(json.dumps(results,indent=2)+'\n')
raise SystemExit(any(r['returncode'] for r in results))
