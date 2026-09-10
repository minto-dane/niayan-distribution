# 原本差集合の供給記録と保存障害試験

2026-09-10 UTC。基準root commitは`32a076d`。最終検証対象source subjectは
`6c6fb59c99442dd2973c420403ee37a3dd9e1ac7a10fcecdeda340a1444a8b2d`。
この証跡は内部SDKと候補CAS保存経路の受入であり、稼働OSの公開・起動切替の認定ではない。

## 実装と境界

`Pkg_Supply_Map`は候補catalogから基準catalogの原本集合を引き、必要な署名付き供給記録と
完全一致することを検査する。NIASMAP1はroot identity、基準descriptor/closure、候補catalog/closure、
整列した元DEB/control/receiptのhashを結ぶ。独立authority、元原本、署名、期限を検査し、
失敗したPrepareでは返却addressと有効期限をzeroにする。不変原本に新しいmirror掲載を要求しない。
履歴保持の構造検査は、新規導入に必要な署名・鮮度検査を代替しない。
仕様は../../../native/supply-map.ja.md、ADR-0079、REQ-119、HAZ-105、FAULT-119。

実root.stateからの基準選択、manifest経由の認可対象計画への束縛、typed GC、製品trust配備は未完。
新規admissionと、既に記録されたtransactionの復旧を区別する永続規則が次に必要である。
本番DEB規模での性能は未測定。共有Packages/InRelease/keyringの反復hashとcatalogの再観測は
静的に確認できる処理であり、大規模更新の実測と共有検査の設計が必要である。

## 最終検証

| 検証 | 結果 |
| --- | --- |
| 標準engineering | 120工程、73 Ada main、18アプリ成功 |
| 新規map driver | 730 assertion成功、UID0では5 assertion成功 |
| 実TUF/OpenPGP → native map | 40 assertionと独立wire preimage照合成功 |
| 固定native image | 359試験成功、skipなし（工具173/native166/hardening4/image16） |
| host source | 24工程成功 |
| 標準・host内のPython | 各597試験発見、11 skipを明記 |
| 私有D-Bus | 32+10試験成功、実UI受入ではない |
| 独立パス等での再現性 | 31 pkgcore実行ファイルと18アプリが同一 |
| ELF hardening | 31ファイルのPIE/RELRO/NOW/NX等を確認 |
| Sanitizer | C境界のASan/UBSanでmap 730 assertionと実署名接続成功 |
| 独立上流比較 | 898場合で不一致0、実script/phase実行ではない |
| 形式証明 | 七つの数学的入力集合が不変、再実行なし。新runtimeはSPARK対象外 |

`qualification.json`は11個の上位検査のlog hashを持つ。`standard/`と`host-source/`には
個々の工程とsource subjectを保持する。`workspace-inputs.json`の3370入力を元repoと
独立コピーで照合した。検証後の引継ぎ文書差分は`handoff-only-changes.json`に記録する。

初期driverの712 assertion成功は`diagnostic-01/`に保持した。標準工程が一度通過した後、
Adaの最高添字に配置した正規singletonを追加して検査すると、終端加算overflowにより
INDETERMINATEとなった。誤成功ではなく正常入力の誤拒否である。`boundary-failure/`に実失敗を保持し、
絶対添字の終端加算を消費件数へ変更した。`boundary-fixed/`は修正後730 assertionの実行である。
`before-boundary-regression/`は以前のsubject
`d659e51f2f5fe2bb036acb7908bb71405b8eab74b0ab97876c2a0335f8084d16`の成功記録であり、
最終ソースの成功として数えない。修正後に全標準工程・独立build・sanitizerを改めて完了した。

## 破壊的カオス試験

実署名fixtureから作った専用の小さいCASを場合ごとにコピーし、実write/rename/fsync/readへの
注入到達をstraceで確認した。システム時計、共有ホストデータ、実ディスクは変更していない。

| 故障 | 完了件数 |
| --- | ---: |
| EIO/ENOSPC | 13 |
| SIGKILL | 13 |
| map反転・切断・欠損 | 6 |
| 必須参照の欠損 | 18 |
| store構造の欠損 | 8 |
| 期限を超えるread/fsync遅延 | 8 |
| SIGKILL後の追加破損 | 4 |
| 合計 | 70 |

seed 20260910は34件、20260911は36件。hashで決まるshardが既存か新規かによって
到達するfsyncが一つ増減するため件数が異なる。注入できなかった場合を成功に数えていない。
二つのcampaignは共に初回完了。誤成功は観測0。期限超過時は、map保存が既に終わっていても
呼出しは失敗し、返却address/期限がzeroになることを確認した。

明示的な隔離・原本/構造の復元後、PrepareとVerifyで同じ正規mapへ戻る時間は
中央値950.281 ms、p95 1039.518 ms、最大1120.489 ms（70件、順位方式はretain.py）だった。
これは小fixtureのlab値であり、本番性能目標や自動復旧時間ではない。隔離・復元は試験器の明示操作。
強制終了後の未参照incomingは残り得るため、有界な回収が別途必要である。

`chaos/summary.json`、各attemptのreport、注入trace、失敗/再開log、公開fixtureを保持した。
`audit-chaos.py`は公開Ed25519署名、六つの原本hash、正規map、実到達した故障、
失敗出力と同じmapへの回復を独立に読み戻す。`chaos/audit.json`に70件の成功を保持する。
物理電断、受理済み公開計画、WAL全経路、実root/boot、全DEB効果の検証ではない。

## 再実行条件

固定開発imageは`sha256:4ec0d3adaef0afc8ce1eccdb621d46911ea2ebc11ddaa9e86f15e4ce59776d4c`、
native imageは`sha256:b626ca976c8ba342df3377e3ad068e29bf45b4c3ad0f7f8927f0551dd09c07dd`。
全重工程は`dev/run-limited.sh`で3 GiB、swapなし、CPU 1、pids128、JOBS=1を維持した。
containerはnetworkなし、UID1000。障害計測だけSYS_PTRACE/DAC_READ_SEARCHを隔離containerへ追加した。
製品のdump禁止は変更していない。この追加権限下の試験を通常DAC/LSMの認定に数えない。
straceとlibunwindのversion/hashは`chaos/injection-tools.json`等にあり、工具実行物は同梱しない。

`prepare.py`、`qualify.py`、`compare.py`、`run-container.py`、`run-chaos-container.py`、
`run-sanitized.py`、`finish.py`は実行時の作業配置を記録する。再実行では独立した新規workを用意し、
これらのroot/work参照と固定imageを合わせる。原本repoを障害対象に渡さない。
chaos driverは隔離container内で`gprbuild -p -P /evidence/chaos/chaos.gpr -j1`、campaignは
同じrunner経由で`python3 -B /evidence/chaos/campaign.py --seed 20260910 --output /evidence/chaos/attempt-01`
として実行した。PYTHONPATHはworkspaceのdistribution/native、tools、testsを含む。
各campaignは現在時刻で新しく署名fixtureを発行する。保存済みreceiptが失効していても
ホスト時計を戻したり検査を省略したりしない。鍵の秘密部は証跡に保存しない。

SHA256SUMSはこのREADMEを含む保持ファイルを列挙する。Git indexのbytesも別途照合してからcommitする。
完全置換ISO、実機受入、全言語翻訳を完了したという主張は含まない。
