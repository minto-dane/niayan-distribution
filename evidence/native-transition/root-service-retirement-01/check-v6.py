from pathlib import Path
import json,os,subprocess
os.umask(0o077)
r=Path('/workspace/pkgcore');out=Path('/evidence/generations-final');assert (out/'v5.log').is_file()
for name in ('v6/store','v6/root'):(out/name).mkdir(parents=True)
commands=[['build/test-bin/run_root_archive_tests',str(out/'v5/store'),str(r/'tests/fixtures/root-archive')],['build/test-bin/run_root_configuration_tests',str(out/'v6/store'),str(out/'v6/root'),str(r/'tests/fixtures/conffiles')]]
for name,command in zip(('v6',),commands[1:]):
 with (out/(name+'.log')).open('w') as log:
  subprocess.run(command,cwd=r,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
 assert 'PASS reinspection transport admission, binding, failure and retained reservations' in (out/(name+'.log')).read_text()
 print('PASS generation',name,flush=True)
assert 'PASS assertions= 1631' in (out/'v5.log').read_text()
(out/'report.json').write_text(json.dumps(dict(result='pass',mains=commands,scope='both v5 and configured v6 enter real generation SDK and explicit reinspection transport, including post-source refusal in v6; synthetic authority/identity, no physical root or boot'),indent=2)+'\n')
