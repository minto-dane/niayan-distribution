# 専用ext4 bankの書込排他

`root_freeze.FrozenRoot`は独立した特権controller用の内部部品である。管理CLIや認可サービスではない。
controllerは事前にbank・世代・workerを認可し、Bankの予約、mount管理とraw deviceへの特権書込の排他を
handleのClose後まで維持する。SDKの世代/root/CAS予約や供給認証を代替しない。

## 対象と操作

対象は明示的に選ばれた専用ext4 filesystemのroot directoryだけである。期待mount ID/device/inodeを
controllerから受け取り、保持FDとkernelのmountinfoへ照合する。bankはroot所有0700、nodev/nosuid/noexec、
ext4 root inode 2、mount root `/`でなければならない。現在の`/`と同じdevice、subtree、子mount、
未対応mount flagは拒否する。旧標準のbind bankを専用領域と誤認して再mountしない。
容量確保・初期化・device identityの永続的な配備は独立installerの責務で、本APIはdeviceを作成/formatしない。

元のextracted記録、worker hash、intentの全選択field、実CAS leaseとarchive FDを照合する。
root FDを開き、同じbank mount上にあることを確認した後、MS_REMOUNT|MS_RDONLYを使う。
MS_BINDを指定せずfilesystem superblock自体をread-onlyにする。nodev/nosuid/noexecを維持し、
atime flagsはkernelの既存値を保持する挙動を使う。それ以外の変更可能flagの採用外profileは拒否する。

Linuxはsuperblockのread-onlyを同じfilesystemの他mountにも適用し、書込FDが残る場合のremountを
拒否する。この違いは[Linux mount(2)](https://man7.org/linux/man-pages/man2/mount.2.html)に従う。
別viewだけをread-onlyにするbind remountはこの部品では使わない。mount syscallの成功後にmountinfoの
superblock側の`ro`と対象FDを再確認する。kernel内のI/O待ちに厳密な実時間上限があるとは主張しない。
controllerは別途プロセス/cgroupの有界な監視を行い、期限超過や不確定結果から自動復旧しない。

Bankのbank.lockはO_RDONLYで開いたFDによる排他flockへ変更する。ファイルのowner/mode/linksの検査と
排他自体は維持する。不要なO_RDWR FDがread-only移行を妨げず、read-only bankの再起動時にも予約できる。
既存サービスのCAP_SYS_ADMIN権限は増やしていない。freeze用RPCや自動停止・再開処理は追加していない。

## 現在観測と寿命

`observe(archive_fd, lease_fd)`は期限・実CAS予約・filesystemの現在のread-only状態・親/rootのidentity・
元intent/resultを再確認し、元展開期限と実rootのmount/device/inodeを返す。これは再検査workerの応答から
期待値を作る経路ではない。実treeの内容と属性は引き続きBank.verify/native Reinspectで照合する。
別viewの通常writerはfilesystem read-onlyで排除できるが、特権remount、raw block/loop backingへの書込、
mount変更、device再割当てをこの観測だけで禁止したとはしない。controllerの排他と効果直前の再観測が必要である。

`close()`は自分のFDと観測だけを閉じ、借用Bank/CASやfilesystemを解錠・thawしない。
成功したread-only移行の後に失敗してもread-only状態を維持する。writerを強制終了する、busyを無視する、
sysrqを使う、filesystemを修復する、暗黙にremount,rwする処理はない。期限切れでも自動thawしない。
このhandleは再起動を越える許可や永続commitではない。再起動後は元記録から新しく予約・照合する。

## 検証と配備境界

`native/worker/check_root_freeze.py`は明示した使い捨てext4 bankだけを対象とする。誤identity、subtree、
子mount、開いた書込FD/書込mmapの拒否、別mountからの書込不能、実worker再検査、read-only bankでの
排他/再起動、Closeによる非thaw、明示した特権remount後の拒否を確認する。
旧SDK直結serviceのfixture bridgeはADR-0120で廃止した。SDKの予約/期限試験は
root_archive_stage_test.adb、実session/worker/凍結はcheck_root_session.pyへ分離する。
本番SDKと独立観測controllerを接続した受入は未完である。

旧bind bankの自動移行は行わない。完全置換ISOのpartition recipe、認証したcontrollerのRPC/寿命管理、
device/mount排他、実root/boot切替と
段階別復旧は未完である。全DEB効果、GC、完全置換ISO、全言語翻訳も別の未完要件として残る。
