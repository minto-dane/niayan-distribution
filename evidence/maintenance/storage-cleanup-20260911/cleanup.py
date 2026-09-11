# SPDX-License-Identifier: BSD-3-Clause
"""One authorized cleanup of explicitly inventoried disposable outputs."""
from pathlib import Path
import json, os, shutil, stat
work=Path('/home/nia/devbox/niaos/.work'); lab=work/'cleanup-20260911'
plan=json.loads((lab/'plan.json').read_text())
files=[work/row['path'] for row in plan['files']]
dirs=[work/name for name in plan['directories']]
targets=files+dirs
raw=(lab/'retained-qcow-info.log').read_text()
info=json.loads(raw[raw.index('\n{')+1:])
for name,meta in info.items():
    backing=meta.get('backing-filename')
    assert backing is None or (name=='distro-builder-vm/builder.qcow2' and backing=='base.qcow2')
    assert work/name not in targets
for p in targets:
    assert p.resolve()==p and p.is_relative_to(work) and p.exists()
    assert not p.is_relative_to(work/'native-configured-publication-01')
for p,row in zip(files,plan['files'],strict=True):
    z=p.stat(); assert (z.st_ino,z.st_size,z.st_uid)==(row['inode'],row['size'],row['uid'])
    assert stat.S_ISREG(z.st_mode)
restricted=[]
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:
        command=(proc/'cmdline').read_bytes().split(b'\0')[0]
        assert b'qemu-system' not in command, 'VM still running'
        for fd in (proc/'fd').iterdir():
            try: value=Path(os.readlink(fd))
            except (FileNotFoundError,PermissionError,ProcessLookupError):continue
            assert not any(value==p or value.is_relative_to(p) for p in targets), 'output still open: '+str(value)
    except PermissionError:
        restricted.append(int(proc.name))
    except (FileNotFoundError,ProcessLookupError):continue
before=os.statvfs(work);removed=[]
for p in files:
    z=p.stat();p.unlink();removed.append(dict(path=str(p.relative_to(work)),kind='disposable-image',allocated=z.st_blocks*512));print('removed',p.relative_to(work),flush=True)
for p in dirs:
    allocated=0;count=0
    for base,children,names in os.walk(p,followlinks=False):
        allocated+=os.lstat(base).st_blocks*512
        for name in names:
            allocated+=os.lstat(Path(base)/name).st_blocks*512;count+=1
    shutil.rmtree(p);removed.append(dict(path=str(p.relative_to(work)),kind='generated-build-cache',allocated=allocated,files=count));print('removed cache',p.relative_to(work),flush=True)
after=os.statvfs(work)
report=dict(result='pass',removed=removed,free_before=before.f_bavail*before.f_frsize,free_after=after.f_bavail*after.f_frsize,reclaimed_available=(after.f_bavail-before.f_bavail)*after.f_frsize,preserved=plan['preserve'],qemu_running=False,open_file_check='no candidate in visible process descriptors; completed private outputs only',restricted_process_descriptors=restricted,source_files_removed=False,sealed_evidence_removed=False)
(lab/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print('reclaimed available GiB',report['reclaimed_available']/1024**3,flush=True)
