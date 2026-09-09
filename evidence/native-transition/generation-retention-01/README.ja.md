# 世代へ束縛したcatalog保持の検証

NIAGEN02によるcatalog保持hashの束縛、stage/publication/native観測の欠落検査を検証した。
全体完成や実起動の受入ではない。正確なsource subjectと集計は`report.json`、実行条件は`commands.json`。
実装判断は[ADR-0074](../../../../assurance/docs/engineering/adr/ADR-0074.ja.md)、
[仕様](../../../native/generation-retention.ja.md)を参照。

## 実行結果

- 全workspaceの116工程、18アプリ、71 Ada main、私有D-Bus 32+10試験が成功。
  Python単体試験は580件発見、source実行11件skip。skipを成功実行に数えない。
- 世代stage1193・公開/復旧1133 assertions。二つのcatalogに5/7 objects、保持一覧240/304 byte。
  五境界でclosure自身と全掲載memberを欠落させた64通りを、独立readerでも実行集合まで照合した。
- v1構造形式の維持、v2 codecと独立transaction vector、旧形式公開拒否、失敗出力、期限切れと
  認可callback中の期限切れを検査。いずれの欠落も再生成で隠さず、確定済み状態を保つ。
- 同じ全体buildのpkgcore単独CI全25 mainと独立oracle、上流との898ケース比較が成功。
- pkgcore29実行ファイルと全18アプリが、別path・mtime・TZの独立buildで一致。ELF検査も成功。
  全体runnerはSOURCE_DATE_EPOCH/TZを子へ渡さず、二回目のbuildには明示した環境差がある。
  pkgcore729入力を4コピー、workspace3344入力を3コピーで比較した。
- root拒否8本とASan/UBSanリンク下のstage1193・publication1133 assertionsが成功。
  C境界とallocator/library-call interceptionの検査であり、Ada・上流library本体は非計測、leak検査は無効。
- 既存7repoのproof入力集合は不変。変更したruntimeはSPARK対象外で、新規形式証明とは数えない。
  host側source24工程も全体検査と同じ前後source subjectで成功した。

## 記録

`workspace-checks/`と`source-checks/`に全実行ログとsubjectを保存した。
`reference-snapshot/`は二世代の照合に実際に使った21個のCAS object、pin、stateと合成rootの
必要部分を保持する。journal全体の代替ではない。`readers/`の独立Python readerで再照合できる。
この合成rootのtree/versionはcatalogのbyte列で、元DEB payloadの物理適用ではない。

このディレクトリから、次のコマンドで保存した参照関係を照合できる。

```sh
python3 -B readers/compare_current_catalog.py \
  --root reference-snapshot/root --state reference-snapshot/state \
  --cas reference-snapshot/cas --bank reference-snapshot/bank \
  --media reference-snapshot/media --native reference-snapshot/native.log \
  --output /tmp/nia-generation-retention-check.json
```

`attempts/`には初期診断と失敗を残した。debug-02で期限検査が成功statusを残す回帰を既存の
不正hash拒否試験が検出し、明示的なDeniedへ修正した。debug-03では遅延認可の呼出し回数を
1回と決めた試験が失敗した。Managed内の再認可は8回であり、1回以上到達したことと
Stale・状態不変を検査するよう修正した。debug-04と独立reader、その後の新規全体buildが成功した。
各診断の入力hash一覧と変更対象sourceを併記し、失敗したbuildを最終成果物に数えない。

`handoff-only-changes.json`はqualification後のAGENTS/STATUS更新だけを記録する。
これらはengineering subjectと実行ファイルの入力から除外される。全保存ファイルのhashは`SHA256SUMS`。

## 残る範囲

全OSと最大容量、全履歴・効果・認証・復旧rootの保持、保持期間・安全なGC、本番の認証済み予約、
保護移行/初期構築、実行phase・所有権/alias・全効果、実root/boot、完全置換ISOと全言語翻訳は未完。
テスト用authority、論理公開、旧APT経路のISO受入を、これらの完了として使わない。
