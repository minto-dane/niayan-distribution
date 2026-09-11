# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import json, subprocess, sys
root=Path('/home/nia/devbox/niaos/nia-os-consent')
lab=Path(__file__).resolve().parent
commands=[('engineering-check.json',['assurance/ci/engineering.py','check']),
          ('engineering-lint.json',['assurance/ci/engineering.py','lint']),
          ('unified-audit.json',['assurance/ci/unified-audit.py']),
          ('license-check.json',['dev/check-licenses.py']),
          ('ci-sync.log',['assurance/ci/sync-component-ci.py'])]
subject=lambda: subprocess.check_output([sys.executable,'assurance/ci/engineering.py','subject'],cwd=root,text=True).strip()
before=subject()
for name,args in commands:
 with (lab/name).open('w') as output:
  subprocess.run([sys.executable,'-B',*args],cwd=root,stdout=output,stderr=subprocess.STDOUT,check=True,timeout=120)
 print('PASS',name,flush=True)
after=subject();assert before==after
(lab/'source-checks.json').write_text(json.dumps(dict(result='pass',source_subject_before=before,source_subject_after=after,checks=[name for name,args in commands]),indent=2)+'\n')
