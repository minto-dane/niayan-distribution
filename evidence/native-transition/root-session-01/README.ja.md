# 初回bank準備のcontroller session

source subject: `ad96a946895f429ce1a8ba518a28097c41460e02eeacfd0dabb703348baad971`。ADR-0114、REQ-152、HAZ-138、FAULT-151。

配布用0.6.0にroot supervisor専用のseqpacket RPCを追加した。接続元と各messageのUID0/同じPIDを照合し、
SO_PEERPIDFDでtaskを保持する。明示request・worker/device plan/boot/bank identityと実CAS/archive FDを検査する。
空の専用RO bankだけを対象に永続O_EXCL attemptを同期し、controllerがRWへ変更する。
既存Bank lock OFDを共有する別childをsetprivで7 capabilityへ縮小し、元prepare/verifyを呼ぶ。
RO化と全再検査後にBank/device/rootを保持し、受信CAS/archiveコピーを閉じてからreadinessを返す。
新CAS OFDを使うobserve、明示close、切断、期限切れを扱い、終了時もbankを自動再利用しない。

VM 03で実bootstrap・実ELF workerを通した準備/RO再検査、非root/誤worker/mount/plan/FDの拒否、
CAS再取得とBank保持、observe/close、元tree/記録不変、使用済みbank拒否が成功した。
実再起動後のROと旧writer開始拒否も成功。VM 04の切断とVM 05の期限切れも成功した。
これらのPython module/workerとfixtureは最終buildと同一bytesである。

VM 06では保持中のbankを試験でRWへ変更し、controller cgroup全体をSIGKILLしたところ、
同じcgroup内のExecStopPostまでSIGKILLされ、RO復帰が失敗した。失敗を正常後片付けに数えない。
OnFailureで別cgroupのseal serviceを起動する構成へ修正した。最終packageのVM 07では同じSIGKILLを受けても
別serviceが実deviceを確認してROへ戻し、元tree/記録を保持した。controllerの正常完了記録は作られていない。
新serviceはSYS_ADMIN/DAC_OVERRIDE、128 MiB/swap0/CPU1/Tasks8でRO化だけを行う。
通常close/切断/期限切れを最終unitで再反復したとは主張せず、対応codeの不変と変更した故障経路の受入を分ける。

初回VM 01は実展開に成功したが、prepareとinspectの追加fieldの違いを無視した比較で拒否した。
比較を修正し、初期bankの実extracted/worker記録をVM 03で読取保存した。
VM 02の二重buildは成功したが、診断用globを非root shellで展開したため新試験前に停止した。
rootによる診断へ修正し、再buildせず同じpackageをVM 03–06へ使用した。失敗入力とログを保持する。

最終main DEB/dbgsym/source dsc/source tar.xzは別directory二重buildで同一bytesだった。
31 export入力をsource packageへ、38 runtime fileを正本/既存受入へ照合した。DEB内module/unitも確認した。
最終workerはb55000d2e21d96c8e75a9f36dda4bbcf5c77c9dbf42074fa39b1600b1c113322で不変。
実initializerは以前の受入package 0.1.0+gita3640276f48dを再使用し、app/vendorの不変を照合した。
構造/参照/lint/license/生成CI整合性も成功。Ada全suite/数学的証明やISO buildは反復していない。

3 GiB/swap0/CPU1/pids128、VM 2 GiB/1CPUで順次実行した。全VM jobは終了した。
使い捨てVM差分7個と追加disk7個、計352.71 MiBを削除した。base/受入VM/対応source/package/実行入力/
既存SDKとinitializer buildを保持する。Git証跡にはVM/CAS/binaryや秘密鍵を含めない。

信頼する主体はroot管理面であり、独立したsite admissionや一般利用者consentの検証をRPCへ実装したとはしない。
人工request/fixtureによる受入で、native SDK adapterは未接続。本番認可/取消、外部特権writer遮断、bank slot/GC、
全DEB効果、実root/boot切替・復旧、完全置換ISO、全言語翻訳は未完である。
controllerはhost mount権限を持つ信頼された部品であり完全sandboxではない。物理電断やkernel I/Oの厳密な
時間上限、RW展開の全命令位置でのSIGKILL、全異常条件でのseal成功を認定しない。
