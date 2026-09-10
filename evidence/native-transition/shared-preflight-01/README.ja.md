# 共有原本の前段検査と限定した回帰確認

2026-09-10 UTC。基準root commitは`90ee2dd`。対象source subjectは
`3da6f36e9b51de7ca3b0e35d5658d8e990826dad341917fb123b78c7dd2f043c`。
供給mapの前段検査と構造保持で、呼出し内の有界集合に全必須原本を集め、同じ原本の重複rehashを削減した。
全固有原本の検査前にnative再構築を開始しない。個別署名・独立policy・期限・元DEB/control照合と
catalog/closure再観測は維持した。呼出しをまたぐcache、新規公開API、永続形式やwriterの変更はない。
仕様は[原本差集合map](../../../native/supply-map.ja.md)、ADR-0079、REQ-119、HAZ-105、FAULT-119。

## 比較測定

四つの異なる2 MiB共有原本と、小さい人工DEBの集合を使った。baseline/candidateとも固定image、
同じbenchmark driver、同じ生成入力を使い、1/16/64 packageの各条件を一回ずつ実行した。
全条件でmap/catalog/closureのbytesが一致した。人工署名observerであり、実TUF mirror規模の測定ではない。

| 64 packageでの処理 | 変更前 ms | 変更後 ms |
| --- | ---: | ---: |
| map作成 | 21078 | 14740 |
| map再検証 | 21105 | 14821 |
| 構造保持検査 | 3074 | 72 |

各条件一回のlocal cache上の比較であり、統計的な遅延指標や本番全量性能を主張しない。
16 packageの別のtrace実行で、共有原本ごとの実pread64 bytesを処理範囲別に独立集計した。
作成/再検証は原本ごと48回相当から17回相当、保持検査は16回相当から1回相当へ減った。
個別Verify_Original/Recheck_Originalは現在も独立に検査するため、全処理が固有原本数だけに比例するとは扱わない。
`comparison/benchmark.json`、`read-comparison.json`、生log/traceに数値と入力hashを保存した。

benchmark補助driverの初回buildは未代入変数の警告で停止した。補助変数を明示初期化してから
独立した新しいobject directoryで両版をbuildした。警告を無効にせず、失敗script/logも保存した。
benchmark driverは測定専用で、製品の管理コマンドや署名providerではない。

## 変更に必要な検証

標準工程は初回にディスク容量不足（os-error-28）で失敗した。初回reportは84工程、うち8失敗である。
`initial-standard/`の実記録を保持し、失敗時のlog_bytesと実際に保存できたbytesが違う場合も修正していない。
初回成功76工程についてsource subjectと実log hash/長さを確認したうえで、失敗・未実行44工程だけを再開した。
`standard/report.json`の120工程は二つの実行batchの合成であり、一回の全面再実行と表示しない。
全73 Ada mainと18アプリの必要工程がそろい、map 1088 assertion、公開2023 assertion、
実TUF/OpenPGP→map接続40 assertionを確認した。共有原本の五つの実欠損・明示復元場合を追加し、
前回成功した呼出しの検査が次の欠損を隠さないこと、再構築前の拒否を検査した。

独立buildの31 pkgcore実行物と18アプリのbyte一致、31 ELF検査、実UID0拒否、文書/台帳を確認した。
`qualification.json`は再開後の五つの上位工程を記録する。実供給bridgeは再開した標準工程内に含まれる。
七つの数学的入力集合とC入力は不変で、形式証明とC ASan/UBSanを繰り返していない。
変更のないnative Python/image・私有D-Bus・hostでの重複source工程、以前の134件campaignも再実行していない。
以前の結果は以前のsubjectへの証跡として保持し、今回の実行数へ加算しない。

## 容量回復と再実行条件

使用中ではない、旧ISO 01/03の正確なsize/hashを元build recordと再照合してから、二つのbuild出力を削除した。
7374675968 allocated bytesを解放した。受入済みISO、対応ソース、全build/受入記録は保持した。
`capacity-recovery.json`に正確な対象とhashを保存した。最初のcleanup補助scriptはaccess timeを含む
全stat比較で停止し、削除前だった。size/identity/mode/owner/mtime/ctime等の安定した値を比較するよう修正して実行した。

固定開発imageは`sha256:4ec0d3adaef0afc8ce1eccdb621d46911ea2ebc11ddaa9e86f15e4ce59776d4c`。
重い工程は3 GiB/swap0/CPU1/pids128、JOBS=1で逐次実行した。通常containerはUID1000、networkなし。
trace取得だけ私有containerでSYS_PTRACE/DAC_READ_SEARCHを追加し、製品dump禁止は維持した。
工具はhash識別用の記録を保持し、strace/libunwind実行物を同梱しない。
実ホストの時計・root・ディスク故障を操作した測定ではない。

benchmark入力生成器とhash一覧、両版の完全入力一覧、最終入力と異なる旧ファイル、runnerとlogを保存した。
入力生成・benchmarkは新しい私有directoryを使う。scriptsは記録した固定workspace/imageを前提とする実験手順である。
検証後に更新するroot引継ぎ文書だけの差分は`handoff-only-changes.json`へ記録する。
本番接続、全DEB効果・所有権・root/boot・完全置換ISO・全翻訳の完成を示す証跡ではない。
利用者の最新方針に従い、この比較を区切り、本番デプロイを妨げる実装へ作業を移す。
