# SPDX-License-Identifier: BSD-3-Clause
import hashlib,json,os,subprocess
from pathlib import Path
work=Path('/evidence');original=Path('/workspace/pkgcore');other=work/'independent-source-long/pkgcore'
entries=json.loads((work/'export.json').read_text())
for entry in entries:
 name=Path(entry['path']).relative_to('pkgcore');source=original/name;target=other/name
 raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==entry['sha256']
 target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);target.chmod(source.stat().st_mode&0o777)
subprocess.run(['gprbuild','-P','tests.gpr','-j1','run_operator_authorization_tests.adb'],cwd=other,check=True)
subprocess.run([str(original/'build/test-bin/run_operator_authorization_tests')],check=True)
subprocess.run([str(other/'build/test-bin/run_operator_authorization_tests')],check=True)
a=hashlib.sha256((original/'build/test-bin/run_operator_authorization_tests').read_bytes()).hexdigest()
b=hashlib.sha256((other/'build/test-bin/run_operator_authorization_tests').read_bytes()).hexdigest()
assert a==b,(a,b)
(work/'reproducibility.json').write_text(json.dumps(dict(result='pass',ada_main_sha256=a,source_files=len(entries),independent_build_directory=str(other),full_components_rebuilt=False),indent=2)+'\n')
print('PASS selected Ada executable independent build',a)
