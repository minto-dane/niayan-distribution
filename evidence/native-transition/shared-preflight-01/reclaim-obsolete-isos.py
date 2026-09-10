# SPDX-License-Identifier: MIT
"""Reclaim exactly two unused, superseded build outputs; retain their records."""
import hashlib,json,os,stat,subprocess
from pathlib import Path
w=Path('/home/nia/devbox/niaos/.work');out=Path(__file__).with_name('capacity-recovery.json');assert not out.exists()
assert (w/'distro-artifacts-09').is_dir()
rows=[]
for label in ['01','03']:
 d=w/('distro-artifacts-'+label);record=d/('record-'+label)/'report.json'
 metadata=json.loads(record.read_text());r=next(x for x in metadata['artifacts'] if x['path'].endswith('.iso'))
 p=d/Path(r['path']).name;before=p.lstat();assert stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==r['size']
 h=hashlib.sha256()
 with p.open('rb') as f:
  while block:=f.read(1024*1024):h.update(block)
 assert h.hexdigest()==r['sha256']
 check=subprocess.run(['sudo','-n','fuser','-v',str(p)],capture_output=True);assert check.returncode==1 and not check.stdout and not check.stderr
 after=p.stat();assert all(getattr(before,k)==getattr(after,k) for k in ['st_dev','st_ino','st_mode','st_nlink','st_uid','st_gid','st_size','st_mtime_ns','st_ctime_ns'])
 rows.append(dict(path=str(p),sha256=h.hexdigest(),size=before.st_size,allocated_bytes=before.st_blocks*512,record=str(record),record_sha256=hashlib.sha256(record.read_bytes()).hexdigest()))
report=dict(reason='ENOSPC during retained integration run; superseded ISO 01/03 build outputs, no open users found',latest_iso_and_sources_untouched=True,rows=rows,removed=[])
out.write_text(json.dumps(report,indent=2)+'\n')
for row in rows:
 Path(row['path']).unlink();report['removed'].append(row['path']);out.write_text(json.dumps(report,indent=2)+'\n')
report['free_bytes_after']=os.statvfs(w).f_bavail*os.statvfs(w).f_frsize;out.write_text(json.dumps(report,indent=2)+'\n')
print('Reclaimed',sum(r['allocated_bytes'] for r in rows),'bytes; preserved build records, accepted ISO and corresponding sources')
