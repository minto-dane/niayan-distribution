# SPDX-License-Identifier: MIT
"""Bounded public archive observation, never an installer or production policy."""
import datetime as dt
import json
from pathlib import Path
import sys
import time

import requests

repo = Path('/home/nia/devbox/niaos/nia-os-consent')
sys.path.insert(0, str(repo/'distribution/tools'))
from debian_archive_auth import authenticated_release, verify_release, verify_snapshot, verify_source, hash_table
from deb_archive import deb822, decompress
from nia_common import sha, relative

work = repo.parent/'.work/native-archive-supply-01/official'
work.mkdir()
session = requests.Session(); session.trust_env = False
downloads = []
def fetch(base, name, limit):
    relative(name)
    target = work/name; target.parent.mkdir(parents=True, exist_ok=True)
    with session.get(base+'/'+name, timeout=(10, 30), stream=True, allow_redirects=False) as response:
        assert response.status_code == 200, (response.status_code, name)
        with target.open('xb') as output:
            count = 0
            for block in response.iter_content(65536):
                count += len(block); assert count <= limit, name
                output.write(block)
    raw = target.read_bytes()
    downloads.append({'url':base+'/'+name, 'path':name, 'sha256':sha(raw), 'size':len(raw)})
    return raw

keyring = Path('/usr/share/keyrings/debian-archive-keyring.pgp').read_bytes()
(work/'archive-keyring.pgp').write_bytes(keyring)
regular_keys = ['B8B80B5B623EAB6AD8775C45B7C5D7D6350947F8', '04B54C3CDCA79751B16BC6B5225629DF75B188BD', '41587F7DB8C774BCCF131416762F67A0B2C39DE4']
security_keys = ['05AB90340C0C5E797F44A8C8254CF3B5AEC0A8F0', '5E04A1E3223A19A20706E20F9904613D4CCE68C6']
observations = {}; policies = {}; now = int(time.time())
for pocket in ['trixie', 'trixie-updates', 'trixie-security']:
    security = pocket.endswith('-security')
    base = 'https://security.debian.org/debian-security' if security else 'https://ftp.debian.org/debian'
    raw = fetch(base, 'dists/'+pocket+'/InRelease', 1024*1024)
    policy = {'schema':'org.niaos.debian-trust/v2', 'keyring_sha256':sha(keyring),
              'primary_fingerprints':security_keys if security else regular_keys,
              'minimum_signatures':1, 'max_age_seconds':(90 if pocket=='trixie' else 7)*86400, 'future_skew_seconds':60,
              'release':{'codename':pocket, 'suite':'stable'+pocket.removeprefix('trixie'), 'architecture':'amd64',
                         'components':['contrib','main'], 'inrelease_sha256':sha(raw),
                         'minimum_date':int(dt.datetime(2026,7,1,tzinfo=dt.timezone.utc).timestamp()) if pocket=='trixie' else now-7*86400,
                         'expires':now+86400}}
    (work/(pocket+'-policy.json')).write_text(json.dumps(policy,indent=2)+'\n')
    observations[pocket] = verify_release(work,keyring,policy,now=now); policies[pocket]=policy
    print('Authenticated official Release',pocket,flush=True)

base = 'https://ftp.debian.org/debian'; index = 'contrib/binary-amd64/Packages.xz'; sources = 'contrib/source/Sources.xz'
raw = fetch(base,'dists/trixie/'+index,2*1024*1024)
release,_ = authenticated_release((work/'dists/trixie/InRelease').read_bytes(),keyring,policies['trixie'],now=now)
table = hash_table(deb822(release,max_stanzas=1)[0]['sha256'])
assert table[index] == (sha(raw),len(raw))
packages = deb822(decompress('data.tar.xz',raw,16*1024*1024),limit=16*1024*1024)
selected = [p for p in packages if p['package']=='b43-fwcutter']; assert len(selected)==1
package = selected[0]; assert int(package['size']) <= 4*1024*1024
fetch(base,package['filename'],int(package['size']))
observations['binary'] = verify_snapshot(work,keyring,policies['trixie'],index,package['filename'],now=now)
raw = fetch(base,'dists/trixie/'+sources,2*1024*1024)
assert table[sources] == (sha(raw),len(raw))
source_records = deb822(decompress('data.tar.xz',raw,16*1024*1024),limit=16*1024*1024)
source = [s for s in source_records if s['package']=='b43-fwcutter' and s['version']==package['version']]; assert len(source)==1
for row in source[0]['checksums-sha256'].splitlines():
    if not row.strip(): continue
    digest,size,name = row.split(); assert int(size)<=8*1024*1024
    content = fetch(base,source[0]['directory']+'/'+name,int(size)); assert sha(content)==digest
observations['source'] = verify_source(work,keyring,policies['trixie'],index,package['filename'],sources,now=now)
(work/'observations.json').write_text(json.dumps({'accepted_at':now,'keyring_sha256':sha(keyring),
    'scope':'Official Debian signatures and bytes; locally selected test pins, not provisioned production Nia policy',
    'production_policy_provisioned':False,'installed':False,'downloads':downloads,'observations':observations},indent=2)+'\n')
print('Authenticated original binary and corresponding complete Sources inventory',flush=True)
