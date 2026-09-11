# 設定済み世代の保持・格納と実準備

ADR-0108 / REQ-146 / HAZ-132 / FAULT-145。対象sourceはreport.json。
NIAGEN06は元rootと設定済みroot/保持記録を区別して世代へ束縛する。既存pinを使い、
格納・inspectionと実準備へ通常のVerify_Currentを接続した。source providerは既定拒否で、
CASを取得し直した内側engineでも、効果を始める前に再観測する。

## 結果

- 設定済み世代: 最終358 assertion。有限期限、headerと独立transaction vector、旧形式への
  relabel、source認可/FD欠落/異なる実root、engine実予約での拒否前の無変更、保持欠損の非修復を確認。
- 新プロセスの現在観測13 caseと、原本span/全選択/保持集合を独立照合する6 rootが成功。
- 元root831 assertion、既存stage 1,211 assertion、旧v5公開142 assertionと独立公開oracleが成功。
- 実サービス/workerのVM試験2 case。各367 assertion。空のlocal設定とvendor退避の内容、世代wireと
  保存record/scope/送信tar、設定元の内容保持を照合。展開後認可拒否はIndeterminateで、extractedな
  非公開rootを保持した。VM終了も0。実installed rootやbootの切替は行っていない。
- 構造/link/lint/license/生成CIの検査が成功。401 compile入力、32 fixture、9 Python工具と4 worker sourceを照合。

## 実行物と失敗記録

test-01は4 mainを強制compileし、初期の設定済み試験と旧root/stageを実行した。
その後、共有test helperへv6専用の異なるsourceとtransaction vectorの試験を追加した。
当初のhelperはbefore-source-check/root_archive_stage_test.adb、入力一覧はtest-01-inputs.jsonに保存した。
本体runtimeの入力は全実行で同一。test-03は最終helperを使う2 mainを強制compileし、最終設定済み試験・
現在観測oracleと旧公開variantを実行した。同じ最終driverをVMへ渡した。

test-02は追加試験のFD型取り違えでcompile停止。明示したO_PATH FDを開くよう試験だけを修正した。
test-03の末尾は、全Ada/oracle成功後のVM実行物梱包で停止した。配布パッケージのworker hashを
以前受入した開発用workerと比較したことが原因である。configured-root-01の受入記録に対応する
ed188c4f23f9078ecaecfff829de6f4a53ba533f0a36a77c6189d5a09a9a123dを照合し直した。
worker-inputs.jsonを参照。installed packageの6518709d…と混同しない。worker bytesは変更していない。

VM 01はfixtureディスク作成の権限設定で停止した。VM 02は梱包した媒体directoryの暗黙の権限が
group-writableとなり、SDKの媒体保護が正しく拒否した。梱包へ明示0755 directory recordを追加し、
fixtureのumaskを022へ固定した。VM 03で両caseが成功した。Niaの媒体検査、worker、service wireを緩めていない。
失敗ログ・途中harnessも保持し、失敗を成功に上書きしない。

## 範囲

固定開発/QEMU image、3 GiB RAM・swap0・CPU1・pids128。VMは2 GiB/1CPUで、読み取り用基盤からの
個別overlayと32 MiBの使い捨てext4 loopを使用し、nodev/nosuid/noexecを確認した。全重処理は直列である。
実行物/VM/CAS/秘密鍵はこの証跡へ収録しない。入力source/fixture、実行harness、hash、結果を保持する。
変更のない全suite・形式証明・旧カオス・性能試験は反復していない。

source provider/供給鍵は厳密な人工fixtureで、本番adapterではない。publisherのv4/v5制限は維持し、
v6公開はUnsupportedのまま。適用前source照合を適用後accepted復旧へ流用しない。
本番認可/quiescence、mount identity移行、accepted復旧、GC、全DEB効果、実root/boot、完全置換ISO、
全言語翻訳は引き続き未完である。これは部分接続の証跡であり、ディストリビューションの本番認定ではない。
