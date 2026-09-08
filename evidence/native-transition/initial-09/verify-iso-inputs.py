from pathlib import Path
import hashlib,json,shutil
root=Path('/home/nia/devbox/niaos/nia-os-consent');work=root.parent/'.work'
evidence=root/'distribution/evidence/native-transition/initial-09';base=work/'nia-native-iso-verification-01';extracted=base/'extracted'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
iso=work/'distro-artifacts-09/niaos-0.1.0-amd64.hybrid.iso'
assert sha(iso)=='d4c18dc0e2be653bf11a04db40db95ca0353322010133e068dda274bd4aa314b'
inv=json.loads((evidence/'inventory.json').read_text());actual=extracted/'var/lib/dpkg';assert sha(actual/'status')==inv['status_sha256']
assert {p.name for p in (actual/'info').iterdir()}==set(inv['control_inventory'])
for name,row in inv['control_inventory'].items():
 assert sha(actual/'info'/name)==row['sha256'] and (actual/'info'/name).stat().st_size==row['size'],name
elf=json.loads((evidence/'elf.json').read_text());assert len(elf['checks'])==18 and elf['result']=='pass'
for row in elf['checks']:
 p=extracted/('usr/bin/nia' if row['name']=='nia' else 'usr/libexec/nia/'+row['name'])
 assert sha(p)==row['sha256'],row['name']
config=extracted/'boot/config-6.12.107+deb13-amd64';observed=json.loads((work/'nia-hardening-04/bios/runtime.json').read_text());assert sha(config)==observed['kernel_config_sha256']
report={'result':'pass','scope':'independent extraction from the host completed ISO, exact status/control/ELF/kernel-config rehash','iso_sha256':sha(iso),'status_sha256':inv['status_sha256'],'control_files_rehashed':len(inv['control_inventory']),'elf_rehashed':len(elf['checks']),'kernel_config_sha256':sha(config),'inventory_sha256':sha(evidence/'inventory.json'),'extract_log_sha256':sha(base/'extract.log'),'verifier_sha256':sha(Path(__file__))}
(evidence/'input-verification.json').write_text(json.dumps(report,indent=2)+'\n')
shutil.copy2(base/'extract.log',evidence/'extract.log');shutil.copy2(Path(__file__),evidence/'verify-iso-inputs.py')
print(json.dumps(report))
