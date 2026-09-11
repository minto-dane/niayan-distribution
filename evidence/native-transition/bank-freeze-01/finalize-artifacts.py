# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path
import hashlib,json,re,shutil
root=Path('/home/nia/devbox/niaos/nia-os-consent');lab=Path(__file__).resolve().parent
out=root/'distribution/evidence/native-transition/bank-freeze-01'
subject=json.loads((lab/'source-checks.json').read_text())['source_subject_after']
for case in ('configured','plain'):
 j=json.loads((lab/'vm-test-05'/case/'result.json').read_text())
 assert j['result']=='pass' and j['dedicated_bank_freeze'] and j['frozen_tree_and_records_unchanged']
for name in ('freeze/result.json','bank.json'):assert json.loads((lab/'vm-test-02'/name).read_text())['result']=='pass'
counts={case:int(re.search(r'PASS assertions=\s*(\d+)',(lab/'vm-test-05'/case/'native-prepare.log').read_text()).group(1)) for case in ('configured','plain')}
report=dict(result='pass-with-production-boundaries-open',source_subject=subject,adr='ADR-0112',requirement='REQ-150',hazard='HAZ-136',fault='FAULT-149',
 package_version='0.4.0',two_builds_byte_equal=['main DEB','dbgsym DEB','source dsc','source tar.xz'],
 standalone_freeze_result='vm-test-02/freeze/result.json',bank_regression_result='vm-test-02/bank.json',sdk_results='vm-test-05',assertions=counts,assertion_count_includes_clock_waits=True,
 limits=dict(memory_bytes=3221225472,swap_bytes=0,cpus=1,pids=128,vm_ram_mib=2048,vm_vcpus=1),
 old_sdk_reused=True,sdk_sources_unchanged=True,worker_unchanged=True,full_suites_and_proofs_repeated=False,
 failed_attempts={'vm-package-01':'Package builds passed; fixture mmap changed expected root atime, rejected by unchanged worker. Probe separated from expected root.',
 'vm-test-02':'Controller and Bank passed; SDK request timed out before extraction; initial backing nested on CAS filesystem.',
 'vm-test-03':'Independent bank backing did not resolve SDK wait; first request timeout.',
 'vm-test-04':'Same SDK timeout; live observation captured ext4 fsync/journal wait on persistent guest-backed CAS loop device.',
 'vm-test-05':'Both SDK variants passed with the previous accepted guest RAM-backed ext4 CAS layout.'},
 durable_storage_performance_tested=False,power_loss_tested=False,production_controller_deployed=False,active_root_or_boot_switched=False,
 remaining=['dedicated bank provisioning and durable device identity','authenticated controller RPC and authority lifetime','effect-time freshness and boot switch/recovery','production source/consent/supply providers','all DEB effects','generation GC','complete replacement ISO','all-language translations'])
(lab/'report.json').write_text(json.dumps(report,indent=2)+'\n')
readme=f'''# 専用ext4 bankの書込排他とSDK接続

source subject: `{subject}`。ADR-0112、REQ-150、HAZ-136、FAULT-149。

内部controller部品FrozenRootを配布用0.4.0へ追加した。独立に選択した専用ext4 bankの
mount/device/inode、root所有0700、保護mount、元intent/workerと実CAS予約を照合し、
filesystem全体をread-onlyへ遷移させる。bank.lockはread-only FDの排他flockで保持する。
現在の標準bind bankを自動移行せず、既存serviceのcapabilityやRPCを拡張しない。

VM 02で誤identity/subtree/子mount、開いた書込FD/mmapの拒否、別mountからの書込禁止、
実worker照合、read-only bankの排他/Bank再起動、Close後のread-only維持、特権remount後の
観測拒否が成功した。Bankのpeer/FD/worker/service中断回帰も成功した。
VM 05では設定済み世代{counts['configured']}、通常世代{counts['plain']} assertionが成功した。
件数には時刻待ちを含む。kernel排他と実物観測をnative SDKへ渡し、5種類の観測/認可拒否、
成功・期限切れの三予約保持、使用中handleの拒否、明示Closeと実root/記録の不変を確認した。
応答後のFD後片付けを100 ms遅らせた条件を維持した。試験bridgeは本番providerではない。

VM 01のmain DEB/dbgsym/source dsc/source tar.xzは別directoryの二重buildで完全一致した。
実DEB導入とmodule bytes照合、unit検査を実施し、socketはdisabled/inactiveを維持した。
workerはb55000d2e21d96c8e75a9f36dda4bbcf5c77c9dbf42074fa39b1600b1c113322で不変。
24 export入力をsource packageへ、83 runtime梱包fileを正本/既存受入へ照合した。
401 SDK compile入力と32 fixtureは前工程と一致し、受入済みSDK binaryを再使用した。
構造/参照/lint/license/生成CI整合性も成功。Ada全suiteと数学的証明は反復していない。

初回のmmapは期待rootのatimeを変え、workerが拒否した。mtime不変とatime差分を採取し、
probeを検査対象rootの外へ分離した。検査や期待属性の緩和はしていない。
VM 02–04のSDKは最初の要求前に待ち時間上限へ到達した。VM 04のlive-diagnosis.logで
SDKのext4 fsync/journal待ちを観測した。VM 05は以前の受入と同じguest RAM上のloop backingへ
戻し、同じSDKとmoduleで通過した。VM永続ディスクでの永続化性能や物理電断は未認定である。
失敗時の入力・ログも保持し、失敗を成功件数へ含めない。

外側3 GiB/swap0/CPU1/pids128、VM 2 GiB/1CPUで実行した。全VM jobは終了した。
5回で共有した使い捨てVM差分1個、511.33 MiBを削除した。base/受入VM/対応source/package/
既存SDK buildを保持する。Git証跡にはVM/CAS/binaryや秘密鍵を含めない。

本番installerの専用bank配備、controllerの認証/RPC/寿命と特権mount/device排他、効果直前の
現在性検査、実root/boot切替と復旧は未完である。全DEB効果、GC、完全置換ISO、全言語翻訳も残る。
FrozenRootのCloseはthawせず、再起動を越える許可を発行しない。kernel I/O待ちの厳密な時間上限や、
特権remount/raw block writerへの単独防御は主張しない。
'''
(lab/'README.ja.md').write_text(readme)
out.mkdir(parents=True,exist_ok=False)
files=['README.ja.md','report.json','artifact-check.py','artifact-check.json','source-checks.py','source-checks.json','source-checks.log','engineering-check.json','engineering-lint.json','unified-audit.json','license-check.json','ci-sync.log','storage-cleanup.json','run-container.py','dev-image.id','sdk-runtime-inputs.json','initial-check_root_freeze.py','initial-check_root_preparation.py','before-independent-backing-check_root_preparation.py','finalize-artifacts.py']
files += ['vm-package-01.py']+['vm-test-'+v+'.py' for v in ('02','03','04','05')]+['vm-'+v+'.log' for v in ('01','02','03','04','05')]
for folder in ('vm-package-01','vm-test-02','vm-test-03','vm-test-04','vm-test-05'):
 for p in sorted((lab/folder).rglob('*')):
  if p.is_file() and (p.suffix in ('.json','.log','.buildinfo','.changes') or p.name=='package-sha256.txt'):
   assert p.stat().st_size < 4*1024**2,p
   files.append(str(p.relative_to(lab)))
files.append('package-source/source-inputs.json')
for name in files:
 p=lab/name;target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
all_files=sorted(p for p in out.rglob('*') if p.is_file())
(out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(out))+'\n' for p in all_files))
print('Sealed',len(all_files)+1,'files')
