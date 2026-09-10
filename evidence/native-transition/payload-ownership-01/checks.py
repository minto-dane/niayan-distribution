import json,os,subprocess
from pathlib import Path
os.umask(0o077)
root=Path('/workspace');out=Path('/evidence/final');out.mkdir();os.chdir(root)
checks=[]
def run(name,args):
 with (out/(name+'.log')).open('wb') as log:
  result=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=610,check=False)
 checks.append(dict(name=name,argv=args,returncode=result.returncode));(out/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
 if result.returncode:raise SystemExit(name+' failed; see retained log')
 print('PASS '+name,flush=True)
def case(name,dirs):
 p=out/name;p.mkdir()
 for d in dirs:(p/d).mkdir()
 return p
run('build',['gprbuild','-j1','-P','tests.gpr','run_payload_ownership_tests.adb','run_root_archive_tests.adb','run_generation_stage_tests.adb','run_generation_publication_tests.adb'])
c=case('ownership',['store']);run('ownership',['build/test-bin/run_payload_ownership_tests',str(c/'store'),'tests/fixtures/payload-ownership'])
c=case('root',['store']);run('root',['build/test-bin/run_root_archive_tests',str(c/'store'),'tests/fixtures/root-archive'])
run('root-oracle',['python3','tests/compare_root_archive.py','--media','tests/fixtures/root-archive','--native',str(out/'root.log'),'--cas',str(c/'store'),'--output',str(out/'root-oracle.json')])
c=case('stage',['root','state','store']);run('stage',['build/test-bin/run_generation_stage_tests',*[str(c/d) for d in ['root','state','store']]])
c=case('publication',['root','state','store','bank']);run('publication',['build/test-bin/run_generation_publication_tests',*[str(c/d) for d in ['root','state','store','bank']],'tests/fixtures/selected-catalog'])
run('publication-oracle',['python3','tests/compare_current_catalog.py','--root',str(c/'root'),'--state',str(c/'state'),'--cas',str(c/'store'),'--bank',str(c/'bank'),'--media','tests/fixtures/selected-catalog','--native',str(out/'publication.log'),'--output',str(out/'publication-oracle.json')])
run('root-publication',['python3','tests/check_root_publication.py','--driver','build/test-bin/run_generation_publication_tests'])
