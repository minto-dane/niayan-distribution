from pathlib import Path
import subprocess,json,sys
root=Path('/home/nia/devbox/niaos/nia-os-consent');out=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'assurance/ci'));import engineering as eng
before=eng.source_subject(root);checks=[]
for name,args in [('engineering-check',['assurance/ci/engineering.py','check']),('engineering-lint',['assurance/ci/engineering.py','lint']),('generated-ci',['assurance/ci/sync-component-ci.py']),('runner-regression',['-B','-m','unittest','discover','-s','assurance/tests/engineering','-p','test_engineering.py','-v'])]:
 with (out/(name+'.log')).open('wb') as log:r=subprocess.run([sys.executable,*args],cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=120)
 checks.append(dict(name=name,returncode=r.returncode))
 if r.returncode:raise SystemExit(name+' failed')
after=eng.source_subject(root);assert before==after
(out/'source-checks.json').write_text(json.dumps(dict(source_subject_before=before,source_subject_after=after,checks=checks,result='pass'),indent=2)+'\n')
print('PASS changed registration and source checks; subject',after)
