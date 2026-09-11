# 実root再検査をnativeの予約保持へ接続

source subject: `37634928f5bc298f03d256e58849c9204804ba2974a5cdcef00745ba994cb058`。ADR-0111、REQ-149、HAZ-135、FAULT-148。

Pkg_Root_Preparation.Reinspectは元展開期限からintent hashを再構成し、別の新規期限でverifyを送る。
独立期待mount/device/inode、worker、archiveとcanonical応答全体を照合する。応答に期待値を委ねない。
世代側のgeneric Reinspect_Root_And_Holdは独立Observe_Rootを必須とし、実stage/root/CAS予約の下で
保持内容・現在設定元・認可を前後確認する。成功時だけ専用limited型へ三予約とarchive FDを保持する。
期限切れで観測は無効になるが、予約はCloseまで維持する。使用中handleの暗黙置換を拒否する。

固定SDKで3 mainを強制compileした。最終の実DEB worker 0.3.0とサービスを使うVM 02では、
設定済み世代477、通常世代933 assertionが成功した（時刻待ちのassertion数は実行依存）。
独立観測拒否、誤mount、誤元期限、応答後観測変更、応答後認可拒否を各世代で確認した。
同じ実treeと保存記録の不変、成功時と期限切れ時の三予約保持、使用中再要求の拒否、明示Closeと解放も確認した。
従来の世代処理1,211 assertionも成功した。

VM 01は、応答直後のサービスFD後片付けとnative側のCAS再取得が競合して失敗した。
サービスは受信FDを閉じてからpeerを閉じる。修正した新SDK経路は応答照合後、不一致の場合も含め、
同じ期限でpeer終了まで確認する。VM 02では応答後の後片付けを100 ms遅らせ、順序を意図的に検査した。
通信異常/期限切れ時にworker/serviceがまだFDを保持する可能性は残るため、すべての不確定結果で
即座に全予約を解放したことにはしない。旧展開Requestの応答完了契約は変更していない。
初回入力と失敗ログも保存する。

401 compile入力、32 fixture、4 VM工具を実行workspaceと正本へ照合した。runtime tar内のdriver/工具と
実行binary、実DEB hashも確認した。worker/serviceは前の受入と同じbytesで、再構築していない。
最終workerはb55000d2e21d96c8e75a9f36dda4bbcf5c77c9dbf42074fa39b1600b1c113322。
構造・参照・lint・license・生成CI整合性も成功した。七つの数学的srcと共通vendorは不変で、全suite/証明は反復していない。
新SDK binaryの二重buildやremote CIを実施したとは主張しない。手動VM用Make targetを追加した。

3 GiB/swap0/CPU1/pids128、VM 2 GiB/1CPUで順次実行し、全job終了済み。
今回のVM差分2個、57.14 MiBを削除した。base/受入VMと対応ソース、現行SDK buildを保持した。
Git証跡にはVM/CAS/binaryや鍵を含めず、これらの実行結果・入力hash・再実行手順を含める。

providerのbank/全writer/mount排他はhandle全寿命で借用する契約で、本番providerは未実装である。
Heldだけではprovider取消やmount変更を観測しない。後続controllerの効果直前再検査、実root/boot切替と復旧、
全DEB効果、GC、完全置換ISO、全言語翻訳は残る。fixture bridgeや供給鍵を本番配備しない。
