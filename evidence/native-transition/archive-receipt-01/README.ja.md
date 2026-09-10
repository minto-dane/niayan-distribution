# 認証原本のnative照合と破壊的カオス試験

2026-09-10 UTC。前工程rootは`b8f2677`。対象source subjectは
`5727fd06deab52a4accf7bca5f48d61192df4936271b7e1a659ada887511bc27`。
原本単位のSDKを検証した記録であり、本番稼働・全更新トランザクション・実root/bootの認定ではない。

## 実装

既存TUF/OpenPGP認証を実行した発行器が、独立に指定する署名providerと公開鍵を使い、
有限期限の`NIASUP01`を返す。native側は独立scope/key/epoch floor/時刻で署名を検査し、
policy・元DEB・raw control・InRelease・Packages・keyringの全CAS原本を再検証する。
さらに元DEBからcontrolを再観測し、完全成功時だけ記録のCAS addressを返す。
任意の観測JSONを署名する入口、製品秘密鍵、既定の実行許可は追加していない。
仕様は[archive-receipt.ja.md](../../../native/archive-receipt.ja.md)、ADR-0078。

## 標準検証

固定開発imageは`sha256:4ec0d3adaef0afc8ce1eccdb621d46911ea2ebc11ddaa9e86f15e4ce59776d4c`。
新規workspaceで`make check private-dbus JOBS=1`の118工程、72 Ada main、18アプリの構築が成功した。
私有D-Bus32+10試験も成功。新しいnative driverは789 assertion、実TUF/OpenPGP発行器からの
接続は正常・別鍵・別scope・別control・破損記録の5場合を検査した。失敗の期待は単なる異常終了ではなく、
nativeの明示的拒否で照合する。root拒否は9 driverと発行器で実UID0を使って確認した。

固定native image
`sha256:b626ca976c8ba342df3377e3ad068e29bf45b4c3ad0f7f8927f0551dd09c07dd`の
`make image-check`は工具173・native166・hardening4・image16、計359試験が成功し、skipはない。
13件の新しい発行器試験を含む。標準工程内とhost source検査は各597 Python試験発見・11 skipで、
skipを実行成功に数えない。host source検査24工程、台帳・inventory・lintも成功した。

全3364入力を元repo・新規workspace・独立コピーで照合した。異なるパス・mtime・TZ・
SOURCE_DATE_EPOCHで30 pkgcore実行ファイルと18アプリの実バイト列が一致した。
30実行ファイルのPIE/RELRO/NOW/NXと実行・書込LOADの分離も確認した。
別コピーでC境界をASan/UBSan付きで再構築し、789 assertionと実署名接続5場合が成功した。
Ada本体と外部ライブラリ全体のsanitizer認定ではない。七つの厳密な数学的入力集合は不変であり、
形式証明は重複実行していない。新しいruntimeはSPARK外であり、試験を形式証明と数えない。

`qualification.json`、`standard/`、`host-source/`、比較JSONと各logが対象入力と結果を保持する。
実行後のroot引継ぎ2文書だけの変更は`handoff-only-changes.json`へ分離する。

## カオス試験

標準試験とは別に、実native CASへの書込・同期・原子的rename・読取へ障害を注入した。
seed `20260910`と`20260911`で各92場合、計184場合が完了した。

| 障害 | 完了件数 |
| --- | ---: |
| writeのENOSPC、fsync/renameat2のEIO | 52 |
| システムコール境界でSIGKILL | 52 |
| SIGKILL後、ACK済み原本をさらに破損 | 8 |
| 必須7原本のbit反転・切断・欠損 | 42 |
| 読取600 ms遅延、要求期限200 ms | 16 |
| SIGSTOP・ロック競合・SIGCONT後の期限切れ | 6 |
| lock/objects/incoming/pins構造の欠損 | 8 |

各場合は新規TemporaryDirectory内のCASだけを使い、完了済みbootstrapの後に障害を注入する。
公開fixtureの原本hash、ACK、実際に到達したシステムコール番号・FD path・注入印、
強制終了signal、障害直後のCAS、再開結果を記録した。SIGSTOPは子のpidfdとwaitidで実停止を観測する。
計測対象はUID1000、ネットワークなしの固定コンテナで、PID名前空間をhostと共有しない。
計測器がdump禁止プロセスとproc FDを観測するため、labにのみSYS_PTRACE/DAC_READ_SEARCHを追加した。
製品のdump禁止設定は変更していない。これらの試験は通常権限下のLSM/DAC認定とは区別する。

完成した184場合に誤った成功報告は観測されず、失敗時のBindingは常にzeroだった。
欠損した必須原本を検証処理が再生成して通すことや、壊れた構造を再初期化して正常扱いすることはない。
破損したimmutable addressへの再取り込みは拒否する。破損除去・構造復元は、注入箇所を把握する
labの明示操作であり、製品による自動修復成功とは数えない。元の公開fixtureは全工程後も不変だった。

障害を外した後の再取り込み＋再検証は中央値171 ms、p95 214 ms、最大446 ms。
小さな合成DEBとローカル一時領域の観測値であり、実システムの復旧SLOではない。
強制終了・I/O障害後に未参照のincoming objectが残る場合がある。受理済み原本とは混同しないが、
有界な回収・容量圧迫への対応は今後必要である。物理ディスクの電断・write cache喪失、
WAL全経路、boot切替、全DEB効果のカオス受入は今回の範囲に含まない。

`chaos/summary.json`が集計、`attempt-04/`と`attempt-05/`が完成した二つのcampaign。
それ以前の三試行も保存した。最初の二回は計測権限不足で注入前に停止。三回目は81場合を完了したが、
後半の遅延が注入前に50 ms期限を超えて未成立となった。これらを184件へ加算していない。
要求期限を200 ms、注入遅延を600 msとした再試行では、対象readのDELAYED印とSTALEを両方要求した。
PCの資源上限を増やしたのではなく、試験要求のdeadlineと注入遅延の関係を修正した。

### 再実行

`chaos/chaos_driver.adb`、`chaos/chaos.gpr`、`chaos/campaign.py`は本番コードを変更しない検証adapter。
workspaceを`/workspace`、これらと専用出力を含むlabを`/evidence/chaos`へmountする。
GPRは正確なworkspaceのpkgcore/runtimeとcontractsを構築する。
strace `6.13+ds-1`とlibunwind8 `1.8.1-0.1`をlabへ配置し、hashは`injection-tools.json`と照合する。
`bin`と`obj`はビルド出力で、バイナリそのものは証跡へ複製していない。

```sh
gprbuild -p -P /evidence/chaos/chaos.gpr -j1
PYTHONPATH=/workspace/distribution/native:/workspace/distribution/tools:/workspace/distribution/tests \
  python3 -B /evidence/chaos/campaign.py --seed 20260910 --output /evidence/chaos/new-run
```

必ず`dev/run-limited.sh`による外側のkernel制限を使い、上記の隔離・UID・計測権限条件を維持する。
出力は新規ディレクトリのみ許し、既存試行を上書きしない。seedは障害選択・順序・offsetを再現する。
鍵・署名・期限・CAS一時名は実行ごとに新規生成されるので、公開fixtureのbytesや測定時間の一致は要求しない。
保持したfixtureの時刻を現在時刻へ偽装して有効化しない。再実行では本物の検証・発行処理を行う。

## 初回失敗と環境

`diagnostic-01/`は試験driverのAda型可視性によるコンパイル失敗、`diagnostic-02/`は修正後の
native789 assertion成功と、古い開発imageで実接続に必要なsecuresystemslibが欠けた失敗を保持する。
各input mapと最終入力との差分原本を保存した。古いimage上の成功を最終環境の成功へ流用していない。

同じ固定Debian 13.6/snapshotと依存一覧から開発imageを再構築した。最初の一括APT導入は
3 GiB制限でOOM停止、次の一件ずつの導入はmirrorの503で失敗した。最後は一件ずつ・最初の失敗で停止・
有限の再試行とnetwork timeoutを設定し、成功した。三回分のContainerfile・依存一覧・log・scope journalを
`image-build/`へ保持する。最終imageの実package一覧は`image-packages.log`。
二回目の失敗時ピーク1.3 GiBを、完成imageのピークとは扱わない。最終exportを含むピークは3 GiBだった。
すべての重い処理は一件ずつ、3 GiB・swap0・CPU1コア分・128プロセスのkernel上限を維持した。

保持工具はこの開発環境の実行記録であり、一般的なビルド入口は既存Makefile/CIを使う。
`SHA256SUMS`は証跡の完全性検査であり、製品の信頼anchorではない。

## 残る条件

本番observer/key/policy配備、rollbackに耐えるtrust floor/時計、全公開計画の原本網羅性と
保持閉包・writer予約への束縛は未完。全DEB phase/所有権/効果、物理root/boot、完全置換ISO、
全言語翻訳も未完である。原本単位の成功をAPT完全置換やディストリビューション完成と報告しない。
