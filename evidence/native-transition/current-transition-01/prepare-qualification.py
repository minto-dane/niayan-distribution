"""Copy bounded source inputs into new, disposable qualification trees."""
import hashlib, json, os, shutil
from pathlib import Path
root=Path('/home/nia/devbox/niaos/nia-os-consent')
work=root.parent/'.work/native-generation-transition-01'
previous=root.parent/'.work/native-generation-retention-01'
excluded={'.git','build','evidence','__pycache__'}
inputs={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob('*') if not set(p.relative_to(root).parts)&excluded and p.is_file()}
support=json.loads((previous/'workspace-supporting-docs.json').read_text())
assert len(inputs)>3300
for name in ['workspace','workspace-independent-long-path']:
    tree=work/name; tree.mkdir()
    for relative,digest in {**inputs,**support}.items():
        source=root/relative
        assert not source.is_symlink() and source.stat().st_size<=8*1024*1024
        assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
        target=tree/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        if name!='workspace':os.utime(target,(1788652800,1788652800))
shutil.copytree(root/'pkgcore',work/'sanitized',ignore=shutil.ignore_patterns(*excluded))
for name,data in [('workspace-inputs.json',inputs),('build-inputs.json',{k.removeprefix('pkgcore/'):v for k,v in inputs.items() if k.startswith('pkgcore/')}),('workspace-supporting-docs.json',support)]:
    (work/name).write_text(json.dumps(data,indent=2)+'\n')
print('Copied',len(inputs),'bounded workspace inputs into fresh trees')
