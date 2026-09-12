# SPDX-License-Identifier: BSD-3-Clause
import os,subprocess,json
from pathlib import Path
assert os.getuid()==0 and Path('/run/.containerenv').is_file()
os.umask(0o077)
p=Path('/evidence');out=p/'root-refusal';out.mkdir()
for name in ['root','state','store']:(out/name).mkdir()
with (p/'root-refusal.log').open('w') as log:
 subprocess.run(['/workspace/pkgcore/build/test-bin/run_generation_stage_tests',*[str(out/name) for name in ['root','state','store']]],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
(p/'root-refusal.json').write_text(json.dumps(dict(result='pass',scope='root refuses native preparation/reinspection before either transport or independent observer'),indent=2)+'\n')
