# SPDX-License-Identifier: MIT
from pathlib import Path
import subprocess
w=Path('/evidence');base=w/'focused';base.mkdir(mode=0o700)
for name in ['map','publication/root','publication/state','publication/store','publication/bank']:
 p=base/name;p.mkdir(parents=True,mode=0o700);p.chmod(0o700)
for label,command in [('map',['build/test-bin/run_supply_map_tests',str(base/'map'),'tests/fixtures/selected-catalog']),('publication',['build/test-bin/run_generation_publication_tests',*[str(base/'publication'/n) for n in ['root','state','store','bank']],'/workspace/pkgcore/tests/fixtures/selected-catalog'])]:
 with (w/('focused-'+label+'.log')).open('w') as log:subprocess.run(command,cwd='/workspace/pkgcore',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
print('PASS focused map and actual publication regression')
