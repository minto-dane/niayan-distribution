# SPDX-License-Identifier: MIT
import json,sys
from pathlib import Path
sys.path.insert(0,'/workspace/distribution/tools')
from debian_archive_auth import verify_release,verify_snapshot,verify_source
root=Path('/official');saved=json.loads((root/'observations.json').read_text());now=saved['accepted_at']
keyring=(root/'archive-keyring.pgp').read_bytes();observations={}
for pocket in ['trixie','trixie-updates','trixie-security']:
    policy=json.loads((root/(pocket+'-policy.json')).read_text())
    observations[pocket]=verify_release(root,keyring,policy,now=now)
policy=json.loads((root/'trixie-policy.json').read_text())
binary=next(row['path'] for row in saved['downloads'] if row['path'].endswith('.deb'))
observations['binary']=verify_snapshot(root,keyring,policy,'contrib/binary-amd64/Packages.xz',binary,now=now)
observations['source']=verify_source(root,keyring,policy,'contrib/binary-amd64/Packages.xz',binary,'contrib/source/Sources.xz',now=now)
assert observations==saved['observations']
print('PASS exact offline replay: three official Releases, original DEB and complete associated Sources inventory; observation time fixed, no installation')
