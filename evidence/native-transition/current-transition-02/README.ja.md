# 更新計画の全体検査と、小さい資源制限試験の分離

前工程の`current-transition-01`で実装した更新計画について、未成功だった標準の
全体検査を完了した。今回の結果は`report.json`とsource subjectへ束縛した実行ログを正本とする。
本番認可、DEB payloadの物理適用、実起動、APT完全置換の認定ではない。

## 検査用の資源枠

前工程では小さい人工プロセスのRLIMIT_ASだけを128 MiBへ限定し、合計RSS上限は
実証明用の既定2048 MiBを継承していた。そのため試験にも開始時4096 MiBが必要だった。
人工プロセスの合計RSS上限も128 MiBへ厳しく限定した。既存のRSS超過試験はさらに40 MiBに限定する。
ホスト予備メモリは2048 MiBを維持し、小さい試験にも2176 MiBの開始条件と実際のメモリ監視を適用する。

17件のguard試験は、子孫への制限継承、過大割当拒否、同時起動拒否、合計RSS、
timeout、signal、複数世代の子孫回収を含む。終了と回収は実際の小さいプロセスで確認する。
追加した二つの境界試験はメモリ不足を模擬して、試験用・実証明用のどちらも子を起動しないことを確認する。
通常成功試験の利用可能メモリは模擬しない。実証明の開始4096 MiB、合計RSS2048 MiB、
予備2048 MiB、guard実装、外側cgroup制限を変更していない。
詳細はADR-0054、REQ-095、FAULT-092を参照する。

## 実行と再現性

新規workspaceで標準`make check private-dbus JOBS=1`を実行し、全116工程、
18アプリ、71 Ada mainと私有D-Busの32+10試験が成功した。
Python単体試験は582件発見し、source実行の11件skipは成功した実行には数えない。
開発基盤の単体試験は134件。ホストのsource検査24工程も成功し、前後subjectが一致した。

別の新規workspaceでmtime・作業パス・TZを変えて構築し、18アプリとpkgcore29実行ファイルの
実バイト列一致、ELF hardening、入力コピーを照合した。最初の全体runnerは
TZ/SOURCE_DATE_EPOCHを子へ渡さず、独立buildにはPacific/Honoluluと固定epoch1788739200を渡す。
pkgcore729入力は前工程とも完全一致し、今回の29実行ファイルも前工程と同じバイト列である。

そのため単独pkgcore CI、独立reader、root拒否とsanitizerの前工程の証跡は、元のsubjectを保持したまま
`prior-pkgcore-evidence-binding.json`で一致する入力・成果物へ対応付ける。
今回それらを再実行したとは記録しない。今回の全体Ada実行は新しいログとして別に保持した。
公開/復旧1361、stage1193 assertionsが今回の全体実行でも成功した。
前工程のsanitizerはC境界等の検査であり、Ada・上流library本体は非計測、leak検査は無効である。

既存7repoの数学的入力は不変であり、形式証明を重複実行しない。
変更箇所と全guard・scope工具の不変性は`prior-input-comparison.json`、
数学的入力の不変性は`proof-input-comparison.json`へ記録した。

すべての重い工程は一つずつ`dev/run-limited.sh`を通し、memory 3 GiB、swapなし、
CPU一コア分、128 processes、JOBS=1を維持した。以前の失敗ログは書き換えていない。
本番admissionと同じ実行予約への接続、全phase・所有権・効果・世代属性、実root/boot、
完全置換ISO、全言語翻訳は未完である。
