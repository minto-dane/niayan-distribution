# SPDX-License-Identifier: MIT
"""Run only failed/unexecuted registered checks after the ENOSPC interruption."""
import hashlib,importlib.util,json,os,shutil,sys,tempfile
from pathlib import Path
root=Path('/workspace');w=Path('/evidence');old_dir=root/'assurance/evidence/engineering-71munqnc'
sys.path.insert(0,str(root/'assurance/ci'));import engineering as eng
spec=importlib.util.spec_from_file_location('runner',root/'assurance/ci/run-engineering-checks.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
old=json.loads((old_dir/'report.json').read_text());subject=eng.source_subject(root)
assert old['result']=='incomplete-or-failed' and old['source_subject_before']==old['source_subject_after']==subject
assert os.geteuid()!=0
out=w/'resumed-standard';out.mkdir();temporary=Path(tempfile.mkdtemp(prefix='mission-resumed-'));env=runner.clean_env(temporary)
previous={c['name']:c for c in old['checks']};checks=[];count=0
for c in old['checks']:
 if c['result']=='pass' and 'log_sha256' in c:
  raw=(old_dir/(c['name']+'.log')).read_bytes();assert len(raw)==c['log_bytes'] and hashlib.sha256(raw).hexdigest()==c['log_sha256']
report=dict(result='running',source_subject_before=subject,checks=checks,initial_report_sha256=hashlib.sha256((old_dir/'report.json').read_bytes()).hexdigest(),production_approval=False,formal_proof='not-run')
def save(): (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
def adopt(c):
 checks.append({**c,'execution_batch':'initial'});
 if 'log_sha256' in c:shutil.copyfile(old_dir/(c['name']+'.log'),out/(c['name']+'.log'))
def invoke(name,argv,cwd,layer):
 global count
 if name in previous and previous[name]['result']=='pass':adopt(previous[name]);return
 c=runner.run_command(argv,cwd,out/(name+'.log'),env,600)
 c.update(name=name,layer=layer,execution_batch='resume');checks.append(c);count+=1;save();assert c['result']=='pass',(name,c)
try:
 for c in old['checks']:
  if c['layer']=='ada-build':break
  assert c['result']=='pass';adopt(c)
 plan=eng.load_json(root/'assurance/engineering/test-plan.json')['ada_tests']
 for repo in eng.REPOS:
  prior=previous.get(repo+'-compile-all')
  if prior is not None and prior['result']!='pass':
   build=root/repo/'build';assert not build.is_symlink()
   if build.exists():shutil.rmtree(build)
  for label,command in [('compile-all','compile-all'),('application-links','build'),('tests-build','test-build')]:invoke(repo+'-'+label,['make',command],root/repo,'ada-build')
  for test in plan:
   if not test['main'].startswith(repo+'/'):continue
   stem=Path(test['main']).stem;name=repo+'-'+stem
   if name in previous and previous[name]['result']=='pass':adopt(previous[name]);continue
   case=Path(tempfile.mkdtemp(prefix=stem+'-',dir=temporary));args=runner.expand_test_args(test,case)
   invoke(name,[str(root/repo/'build/test-bin'/stem),*args],root/repo,'ada-'+test['tier'])
  if repo=='pkgcore':
   for name,script,driver,layer in [('archive-receipt-native-bridge','check_archive_receipt_bridge.py','run_archive_supply_tests','actual-supply-and-native-cas'),('supply-map-native-bridge','check_supply_map_bridge.py','run_supply_map_tests','actual-supply-and-native-map')]:invoke(name,[sys.executable,'-B',str(root/'distribution/native'/script),'--driver',str(root/'pkgcore/build/test-bin'/driver)],root,layer)
 assert len(checks)==120 and len({c['name'] for c in checks})==120
 assert eng.source_subject(root)==subject
 report.update(result='pass-combined-same-inputs',source_subject_after=subject,resumed_check_count=count,initial_pass_count=len(checks)-count,ada_execution='all-registered-tests-pass-across-two-batches')
finally:
 shutil.rmtree(temporary);report['temporary_io_tree_removed']=True;save()
print('PASS combined 120 checks; reran only',count,'failed or unexecuted checks')
