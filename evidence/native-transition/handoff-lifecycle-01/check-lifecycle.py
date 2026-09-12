# SPDX-License-Identifier: BSD-3-Clause
import json, subprocess
from pathlib import Path
p=Path('/evidence')
with (p/'lifecycle.log').open('w') as log:
 subprocess.run(['python3','-B','-m','unittest','test_handoff_lifecycle','-v'],cwd=p,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
with (p/'model.json').open('w') as out:
 subprocess.run(['python3','-B',str(p/'check_handoff_lifecycle.py')],cwd=p,stdout=out,check=True,timeout=30)
with (p/'optimized-refusal.log').open('w') as out:
 run=subprocess.run(['python3','-O','-B',str(p/'check_handoff_lifecycle.py')],cwd=p,stdout=out,stderr=subprocess.STDOUT,timeout=30)
assert run.returncode!=0
assert 'assertions must be enabled' in (p/'optimized-refusal.log').read_text()
(p/'lifecycle-report.json').write_text(json.dumps(dict(result='pass',fault_tests=10,model=json.loads((p/'model.json').read_text()),optimized_checker_refused=True,complete_runtime_proof=False),indent=2)+'\n')
