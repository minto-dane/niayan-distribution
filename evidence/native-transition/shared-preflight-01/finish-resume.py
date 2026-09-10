# SPDX-License-Identifier: MIT
from pathlib import Path
import subprocess
w=Path(__file__).resolve().parent
for label,script in [('resume-qualification-run','resume-qualification.py'),('comparison-run','compare.py')]:
 with (w/(label+'.log')).open('x') as log:subprocess.run(['python3','-B',str(w/script)],cwd=w,stdout=log,stderr=subprocess.STDOUT,check=True)
print('PASS resumed qualification and comparison')
