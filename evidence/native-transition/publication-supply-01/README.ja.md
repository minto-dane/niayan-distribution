# 供給ポリシーを束縛した世代公開と障害復旧

2026-09-10 UTC。基準root commitは`e05d596`。最終検証対象source subjectは
`a260ae0b1dbe60ba7d88e9057b7edbb2bece78a74a9cc4a9162226d1b62f2a54`。
実際のnative公開計画、root.state、file-WALを使った非特権SDKの検証である。
stageの効果とauthorityは人工fixtureであり、実DEB rootfs・起動切替・本番認定ではない。

## 実装

NIASPOL1は原本差集合map、検査対象UTC観測、scope順の独立key/floor/ageを不変CASへ保持する。
NIAGEN04はこのpolicyを既存descriptor/計画/pinへ束縛し、第二の導入済みDBや別pinを作らない。
新規公開は保持観測から現在までの供給署名・全原本・差集合を検査する。記録済み復旧は
実root.stateの正確なactive/accepted planと全ジャーナルを確認してから、当初の観測で再検査する。
どちらも独立した現在のkey/floor/ageとの完全一致と既存Managed guardを必須とする。
古いCAS記録だけで新規公開を許さず、鍵の失効やfloor引上げを復旧理由で迂回しない。

StageからEngineへの予約受渡し後にも、Engineが実際に保持するroot/CAS予約の下で
全root.state、descriptor、保持原本、intent、供給policyを再検査する。受渡し中の原本欠損を拒否する。
返却直前にも有限I/O期限を検査するため、永続公開後に遅いI/OでSTALEとなる場合がある。
非OKを未実行と解釈せず、正確な計画の観測・再開で判断する。
仕様は[publication-supply.ja.md](../../../native/publication-supply.ja.md)、ADR-0080、REQ-120、HAZ-106、FAULT-120。

## 最終検証

| 検証 | 結果 |
| --- | --- |
| 標準engineering | 120工程、73 Ada main、18アプリ成功 |
| map/policy driver | 1029 assertion成功、実UID0で10 assertion成功 |
| stage/publication driver | 1211 / 2023 assertion成功 |
| 実TUF/OpenPGP → native map | 40 assertionと独立wire照合成功 |
| 固定native image | 359試験成功、skipなし（工具173/native166/hardening4/image16） |
| host source | 24工程成功 |
| 標準・host内のPython | 各597試験発見、11 skipを明記 |
| 私有D-Bus | 32+10試験成功、実UI受入ではない |
| 独立build | 31 pkgcore実行ファイルと18アプリがbyte一致 |
| ELF hardening | 31ファイルのPIE/RELRO/NOW/NX等を確認 |
| Sanitizer | C境界ASan/UBSanで上記3 driverと実署名接続が成功 |
| 独立上流比較 | 898場合で不一致0、実script/phase実行ではない |
| 形式証明 | 七つの数学的入力集合が不変、再実行なし。新runtimeはSPARK対象外 |

`qualification.json`は11個の上位検査とlog hashを保持する。`standard/`と`host-source/`に
個々の工程とsource subjectを保存した。`workspace-inputs.json`の3374入力を元repoと
新規・独立コピーで照合した。検証後の引継ぎ文書差分は`handoff-only-changes.json`で区別する。
実TUFからmapまでの接続と、人工署名observerを使うv4 publisherの検証は別である。
実TUFから本番publisherまでの製品adapterが完成したとは扱わない。

診断01では試験fixtureのtransaction ID衝突を既存pin検査が拒否した。試験IDを分離して修正した。
診断02では独立oracleがcatalog内controlのoffsetを誤読した。同じfixtureを修正oracleで照合した。
診断03では予約受渡し中のpolicy/map/intent欠損3場合を追加して成功した。
各診断の入力一覧、最終入力との相違、失敗log、修正oracleを保存した。製品の検査は弱めていない。

## 破壊的カオス試験

各場合に新しい私有小fixtureを使い、実Prepared→ApplyDoneのactive計画から公開・再開する。
当初の供給観測1000、有効期限1600に対して復旧observerは2000を返す人工時刻であり、
実ホスト時計は変更せず、実時間による供給期限待ちとは区別する。

| 故障 | 完了件数 |
| --- | ---: |
| EIO/ENOSPC | 40 |
| SIGKILL | 40 |
| 必須原本・参照の欠損 | 16 |
| lock/state/journal/pin等の構造欠損 | 14 |
| root.state/journal/policyの反転・切断 | 12 |
| 期限を超えるread/fsync遅延 | 8 |
| SIGKILL後の追加欠損 | 4 |
| 合計 | 134 |

seed 20260910/20260911の完了campaignは各67件。実write/renameat/renameat2/fsync/pread64の
到達をtraceで確認し、未到達注入を成功に数えない。観測範囲で誤成功0。
I/O障害・強制終了から同じ計画を再開し、さらに同じ計画を再実行してaccepted plan不変を検査した。
欠損・破損では明示的に原本をlab復元してから再開した。これは製品の自動修復ではない。
復旧・同じ計画の再実行・native読取検査を合わせた時間は中央値2658.575 ms、p95 2771.439 ms、
最大3136.798 ms（134件、順位方式はretain.py）。全OSの復旧時間や本番性能目標ではない。

`attempt-01`は69場合を完了した後に計測範囲の誤りで停止した未完了campaignであり、上表から除外した。
初期traceは実renameatを選択せず、公開後に試験driverが行うnative読取まで注入対象に含めていた。
修正後は両rename syscallを記録し、最終root.state置換に続く二つのparent fsyncまでを公開範囲とした。
遅延注入の対象も同じ範囲に限定した。未完了結果・元試験器・終了logも保持している。

`audit-chaos.py`は公開鍵を独立に固定し、Ed25519署名、全6原本hash、manifest/policy/map、
plan/pin/descriptorを照合する。故障直後・復旧後の実root.stateとWAL bytesを保存し、
各frameのchecksumと全frame hashによるPrevious鎖、accepted plan、実注入traceを検査した。
初回auditは計画の16 bitパス長を32 bitとして誤読して停止した。元script/logを保持し、
16 bit長・予約領域・パス・全長を厳密に検査する修正版で同じ134件を再照合して成功した。
追加計測権限のない通常の固定containerで独立auditを実行した。

## 再実行と限界

固定開発imageは`sha256:4ec0d3adaef0afc8ce1eccdb621d46911ea2ebc11ddaa9e86f15e4ce59776d4c`、
native imageは`sha256:b626ca976c8ba342df3377e3ad068e29bf45b4c3ad0f7f8927f0551dd09c07dd`。
全重工程は`dev/run-limited.sh`で3 GiB・swap0・CPU1・pids128、JOBS=1を維持した。
containerはnetworkなし・UID1000。注入時だけSYS_PTRACE/DAC_READ_SEARCHを私有containerへ追加し、
製品のdump禁止は変更していない。この計測を通常DAC/LSMの認定には数えない。
工具version/hashは`chaos/injection-tools.json`等に保持し、strace/libunwind実行物は同梱しない。
鍵は既存の公開された人工試験seedであり、本番秘密鍵は含まない。

prepare/qualify/compare、container runner、campaign、audit、retainの各scriptと実行logを保持した。
これらは記録した絶対workspaceと固定imageを前提とする実験手順で、製品の管理コマンドではない。
Git checkoutはfixtureの全0400/0700 modeを復元しない。保存checkpointはbyte証跡として読み、
再実行は入力・工具hashと資源制限を確認して新しい私有fixtureを生成する。

本番Observe_Supply/Managed provider、鍵/policy配備、独立時刻/floor、鍵移行後の復旧、
全DEB効果・実root/boot・大規模性能・全世代GC・完全置換ISO・全言語翻訳は未完である。
未参照CAS/一時ファイルは残り得る。物理電断、disk firmware、実bootは本試験の対象外。
過去のmap保存70件・単一原本184件は別source/別経路であり、今回の134件へ加算しない。
