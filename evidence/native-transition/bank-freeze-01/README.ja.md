# 専用ext4 bankの書込排他とSDK接続

source subject: `df59c0171fd025fea8a5e4437847edb94a2361cbb63bbc880f69862a70c5a210`。ADR-0112、REQ-150、HAZ-136、FAULT-149。

内部controller部品FrozenRootを配布用0.4.0へ追加した。独立に選択した専用ext4 bankの
mount/device/inode、root所有0700、保護mount、元intent/workerと実CAS予約を照合し、
filesystem全体をread-onlyへ遷移させる。bank.lockはread-only FDの排他flockで保持する。
現在の標準bind bankを自動移行せず、既存serviceのcapabilityやRPCを拡張しない。

VM 02で誤identity/subtree/子mount、開いた書込FD/mmapの拒否、別mountからの書込禁止、
実worker照合、read-only bankの排他/Bank再起動、Close後のread-only維持、特権remount後の
観測拒否が成功した。Bankのpeer/FD/worker/service中断回帰も成功した。
VM 05では設定済み世代482、通常世代937 assertionが成功した。
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
