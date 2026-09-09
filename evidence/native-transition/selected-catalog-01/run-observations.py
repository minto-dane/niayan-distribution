# SPDX-License-Identifier: MIT
import json,subprocess
from pathlib import Path
w=Path('/evidence'); binary=Path('/workspace/build/test-bin'); tests=Path('/workspace/tests')
def run(args): subprocess.run([str(x) for x in args],check=True)
def measured(name,args):
 out=subprocess.run(['python3',str(w/'probe-resources.py'),str(w/(name+'.log')),*map(str,args)],capture_output=True,text=True)
 (w/(name+'-resources.json')).write_text(out.stdout)
 print(name,out.stdout,flush=True)
 if out.returncode: raise SystemExit(out.returncode)
def oracle(name,media,listing,payload):
 run(['python3',tests/'compare_selected_catalog.py','--media',media,'--list',listing,'--native',w/(name+'.log'),'--payload-hash',payload,'--output',w/(name+'-oracle.json')])
run(['python3',tests/'make_selected_catalog_fixtures.py','--check'])
run(['python3',w/'probe-all.py','fixture-probes',w/'fixture-media'])
measured('fixture-index',[binary/'run_payload_index_tests',w/'index-cas',w/'fixture-media',w/'fixture-list.txt','--scan'])
run(['python3',tests/'compare_payload_index.py','--media',w/'fixture-media','--probes',w/'fixture-probes','--index-log',w/'fixture-index.log','--output',w/'fixture-index-oracle.json'])
payload=json.loads((w/'fixture-index-oracle.json').read_text())['index']['INDEX']
measured('catalog-fixtures',[binary/'run_selected_catalog_tests',w/'accepted-cas',tests/'fixtures/selected-catalog'])
oracle('catalog-fixtures',w/'fixture-media',w/'fixture-list.txt',payload)
measured('catalog-reverse',[binary/'run_selected_catalog_tests',w/'reverse-cas',w/'fixture-media',w/'fixture-reverse.txt','--scan'])
oracle('catalog-reverse',w/'fixture-media',w/'fixture-reverse.txt',payload)
measured('catalog-originals',[binary/'run_selected_catalog_tests',w/'scan-cas','/originals',w/'original-list.txt','--scan'])
payload=json.loads((w/'reference-original-index.json').read_text())['index']['INDEX']
oracle('catalog-originals',Path('/originals'),w/'original-list.txt',payload)
