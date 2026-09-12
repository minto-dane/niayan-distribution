set -eu
test -f /etc/niaos-image-builder
python3 - <<'PY'
from pathlib import Path
import hashlib,json,os,shutil,tarfile
paths=[Path('/build-'+str(i).zfill(2)) for i in range(3,10)]
for p in paths:
 assert p.is_dir() and not p.is_symlink()
for line in Path('/proc/self/mountinfo').read_text().splitlines():
 mount=line.split()[4]
 assert all(mount!=str(p) and not mount.startswith(str(p)+'/') for p in paths),mount
archive=Path('/build/retired-build-records-20260912.tar.xz');assert not archive.exists()
status=hashlib.sha256(Path('/var/lib/dpkg/status').read_bytes()).hexdigest()
with tarfile.open(archive,'x:xz') as t:
 for p in paths:
  for item in sorted(p.iterdir()):
   if item.name.startswith('record-') or item.is_file() and item.suffix in ('.json','.txt','.log'):
    t.add(item,arcname=str(item.relative_to('/')),recursive=True)
record=dict(removed=[str(p) for p in paths],preserved_records=str(archive),records_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),installed_packages_sha256=status)
print(json.dumps(record,indent=2),flush=True)
for p in paths:shutil.rmtree(p)
assert hashlib.sha256(Path('/var/lib/dpkg/status').read_bytes()).hexdigest()==status
Path('/build/retired-build-cleanup-20260912.json').write_text(json.dumps(record,indent=2)+'\n')
PY
fstrim -v /
df -B1 /
