# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import hashlib,io,json,stat,subprocess,tarfile
root=Path('/home/nia/devbox/niaos/nia-os-consent');lab=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
manifest=json.loads((lab/'package-source/source-inputs.json').read_text())['files']
packages=lab/'vm-package-01/packages';main=packages/'niaos-root-preparation_0.8.0_amd64.deb'
with tarfile.open(packages/'niaos-root-preparation_0.8.0.tar.xz') as archive:
 for name,item in manifest.items():
  raw=(root/'distribution'/item['source']).read_bytes();assert sha(raw)==item['sha256'],name
  selected=[m for m in archive.getmembers() if m.isfile() and m.name.endswith('/'+name)]
  assert len(selected)==1,name
  assert archive.extractfile(selected[0]).read()==raw and stat.S_IMODE(selected[0].mode)==item['mode'],name
with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['dpkg-deb','--fsys-tarfile',str(main)]))) as archive:
 delivered={m.name.removeprefix('./'):archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()}
 for name in ('root_bank.py','root_freeze.py','bank_device.py','storage_bootstrap.py','root_session.py','root_session_worker.py'):
  assert delivered['usr/libexec/niaos/'+name]==(root/'distribution/native'/name).read_bytes(),name
 for name in ('niaos-root-bank-check.service','niaos-root-session.service','niaos-root-session.socket','niaos-root-session-seal.service'):
  assert delivered['usr/lib/systemd/system/'+name]==(root/'distribution/packaging/root-preparation/debian'/name).read_bytes(),name
 assert delivered['usr/lib/systemd/system/var-lib-niaos-roots.mount']==(root/'distribution/packaging/root-preparation/deployment/var-lib-niaos-roots.mount').read_bytes()
 assert not any('niaos-root-preparation.service' in n or 'niaos-root-preparation.socket' in n or '/root-preparation/dev/' in n for n in delivered)
 assert b'def serve(' not in delivered['usr/libexec/niaos/root_bank.py']
 assert b'def connection(' not in delivered['usr/libexec/niaos/root_bank.py']
with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['dpkg-deb','--ctrl-tarfile',str(main)]))) as archive:
 preinst=archive.extractfile('./preinst').read()
 marker=b'#DEBHELPER#'
 raw=(root/'distribution/packaging/root-preparation/debian/niaos-root-preparation.preinst').read_bytes()
 assert preinst.startswith(raw.split(marker)[0])
 assert preinst.index(b'upgrade requires an offline target') < preinst.index(b'# Automatically added')
old=lab.parent/'native-operator-authorization-01/vm-package-01/packages/niaos-root-preparation_0.7.0_amd64.deb'
with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['dpkg-deb','--ctrl-tarfile',str(old)]))) as archive:
 assert './prerm' not in archive.getnames()
# Exact sources and fixtures used by the selected native builds.
compile_inputs={}
for item in json.loads((lab/'export.json').read_text()):
 if not item['path'].startswith('pkgcore/'):continue
 source=root/item['path'];snapshot=lab/'workspace'/item['path']
 assert source.is_file() and source.read_bytes()==snapshot.read_bytes(),item['path']
 assert sha(source.read_bytes())==item['sha256'],item['path']
 compile_inputs[item['path']]=item['sha256']
for name in ('runtime/pkg_root_preparation.ads','runtime/pkg_root_preparation.adb','runtime/root_preparation.c'):
 assert not (root/'pkgcore'/name).exists() and not (lab/'workspace/pkgcore'/name).exists()
symbols=subprocess.check_output(['nm','--defined-only',str(lab/'workspace/pkgcore/build/test-obj/libtests.a')],stderr=subprocess.STDOUT)
assert b' nia_root_prepare\n' not in symbols and b' nia_root_reinspect\n' not in symbols
(lab/'compile-inputs.json').write_text(json.dumps(compile_inputs,indent=2)+'\n')
runtime={}
with tarfile.open(lab/'runtime.tar') as archive:
 for member in archive.getmembers():
  if not member.isfile():continue
  raw=archive.extractfile(member).read();runtime[member.name]=sha(raw)
  if member.name.startswith('source/'):
   assert raw==(lab/'package-source'/member.name.removeprefix('source/')).read_bytes()
  elif member.name.startswith('check_'):
   assert raw==(root/'distribution/native/worker'/member.name).read_bytes(),member.name
  elif member.name=='old.deb':assert raw==old.read_bytes()
# The unchanged native initializer is reused, not rebuilt for this scope.
component=lab.parent/'native-storage-bootstrap-01/niaos-pkgcore_0.1.0+gita3640276f48d_amd64.deb'
assert runtime['component.deb']==sha(component.read_bytes())
assert subprocess.check_output(['git','show','a3640276f48d:app/pkg_store_bootstrap.adb'],cwd=root/'pkgcore')==(root/'pkgcore/app/pkg_store_bootstrap.adb').read_bytes()
assert not subprocess.check_output(['git','diff','a3640276f48d','--','vendor'],cwd=root/'pkgcore')
with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['dpkg-deb','--fsys-tarfile',str(component)]))) as archive:
 member=next(m for m in archive.getmembers() if m.name.endswith('/usr/libexec/nia/pkg_store_bootstrap'))
 initializer=sha(archive.extractfile(member).read())
 assert initializer=='1a163c364f589b77f1fc30bc6a4a5f44232c631c9d70b4152ffd4847cf154300'
reports=['native-check/report.json','generations-final/report.json','root-refusal.json','root-session-transport.json',
 'vm-acceptance-02/result.json','vm-acceptance-02/bootstrap.json','vm-acceptance-02/bank.json',
 'vm-acceptance-02/reinspection.json','vm-acceptance-02/upgrade-live-old.json',
 'vm-acceptance-02/upgrade-offline.json','vm-acceptance-02/upgrade-live-active.json']
for name in reports:assert json.loads((lab/name).read_text())['result']=='pass',name
exit_record=json.loads((lab/'vm-acceptance-02/exit.json').read_text());assert exit_record['worker_exit']==exit_record['qemu_exit']==0
for name in ('result.json','bootstrap.json'):
 value=json.loads((lab/'vm-acceptance-02'/name).read_text())
 assert value.get('reboot_readonly_and_old_writer_refused') or value.get('reboot_readonly'),name
for name in ('upgrade-live-old.json','upgrade-offline.json','upgrade-live-active.json'):
 assert json.loads((lab/'vm-acceptance-02'/name).read_text())['new_sha256']==sha(main.read_bytes())
# Two independent build directories compared all main/debug/source artifacts;
# the successful later VM phase reused the already built and installed package.
assert 'cmp build-a/niaos-root-preparation_0.8.0_amd64.deb' in (lab/'guest-build.sh').read_text()
assert json.loads((lab/'vm-package-01/upgrade-offline.json').read_text())['result']=='pass'
result=dict(result='pass',package_sha256=sha(main.read_bytes()),delivered_files={n:sha(v) for n,v in delivered.items()},
 source_files=len(manifest),native_snapshot_files=len(compile_inputs),
 binaries={p.name:sha(p.read_bytes()) for p in (lab/'workspace/pkgcore/build/test-bin').iterdir() if p.is_file()},
 runtime=runtime,old_rpc_symbols_absent=True,old_prerm_absent=True,guard_precedes_generated_helpers=True,
 reused_initializer_sha256=initializer,reports=reports,production_approval=False,complete_formal_proof=False)
(lab/'artifact-check.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS exact source/package/runtime/native artifacts; retired endpoint absent')
