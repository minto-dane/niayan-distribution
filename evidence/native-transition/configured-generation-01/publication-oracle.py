# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import sys,json
sys.path.insert(0,'/workspace/pkgcore/tests')
from compare_root_publication import check
p=Path('/evidence/publication-01')
r=check(p/'root',p/'state',p/'store',p/'bank',Path('/workspace/pkgcore/tests/fixtures/root-archive'),Path('/evidence/publication-test-01.log'))
Path('/evidence/publication-oracle.json').write_text(json.dumps(r,indent=2)+'\n')
print('PASS legacy root publication independent oracle')
