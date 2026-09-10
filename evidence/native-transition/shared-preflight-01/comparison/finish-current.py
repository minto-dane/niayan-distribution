# SPDX-License-Identifier: MIT
from pathlib import Path
import subprocess
w=Path(__file__).resolve().parent
with (w/'trace-benchmark.log').open('x') as log:
 subprocess.run(['python3','-B',str(w/'trace-benchmark.py')],cwd=w,stdout=log,stderr=subprocess.STDOUT,check=True)
q=w.parent/'native-shared-preflight-02'
with (q/'qualification-run.log').open('x') as log:
 subprocess.run(['python3','-B',str(q/'qualify.py')],cwd=q,stdout=log,stderr=subprocess.STDOUT,check=True)
with (q/'comparison-run.log').open('x') as log:
 subprocess.run(['python3','-B',str(q/'compare.py')],cwd=q,stdout=log,stderr=subprocess.STDOUT,check=True)
print('PASS traced comparison and qualification')
