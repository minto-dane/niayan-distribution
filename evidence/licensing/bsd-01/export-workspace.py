from pathlib import Path
import subprocess,shutil,hashlib,json,stat
root=Path('/home/nia/devbox/niaos/nia-os-consent');work=root.parent/'.work/bsd-license-transition-01';dest=work/'workspace';dest.mkdir()
repos=('.', 'assurance','pkgcore','statecore','controlcore','configcore','resolvercore','capsulecore','distribution')
inputs={}
for repo in repos:
 base=root/repo; target=dest/repo;target.mkdir(exist_ok=True)
 names=subprocess.check_output(['git','-C',str(base),'ls-files','--cached','--others','--exclude-standard','-z']).decode().split('\0')
 for name in sorted(set(names)-{''}):
  if any(x in ('evidence','build','__pycache__','.pytest_cache','.git') for x in Path(name).parts):continue
  p=base/name
  if p.is_dir():continue
  info=p.lstat();assert stat.S_ISREG(info.st_mode) and info.st_size<=8*1024*1024,str(p)
  output=target/name;output.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,output)
  inputs[str(p.relative_to(root))]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':info.st_size}
 # Local metadata only for Git-aware source checks. Never reuse host gitdir paths.
 subprocess.run(['git','init','-q',str(target)],check=True)
 subprocess.run(['git','-C',str(target),'add','-f','.'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
(work/'source-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
shutil.copyfile(work.parent/'native-root-preparation-01/run-container.py',work/'run-container.py')
(work/'dev-image.id').write_text('sha256:4ec0d3adaef0afc8ce1eccdb621d46911ea2ebc11ddaa9e86f15e4ce59776d4c\n')
print('Exported bounded source files',len(inputs))
