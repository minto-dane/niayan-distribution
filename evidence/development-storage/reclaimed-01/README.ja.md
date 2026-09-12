# 開発用storageの回収と受入diskの寿命

2026-09-12。ホスト空き約4.1 GiBの主因となっていた開発資産を整理した。
sourceとartifactの保持を、再利用しない実行用diskや古いbuild作業領域と分ける。

| 対象 | 整理前の実割当 | 処置 |
|---|---:|---|
| ISO 09の完了済み導入VM 2台 | 19,430,965,248 byte | 使用中FDとbacking参照なしを確認してdiskだけ削除 |
| builder.qcow2 | 58,834,296,832 byte | guestの/build-03〜/build-09を削除しfstrim |
| builder.qcow2整理後 | 18,490,699,776 byte | 現在の/build、導入済み工具、元cloud imageを保持 |

実割当の減少は計59,774,562,304 byte。`storage-result.json`に空き容量と対象を記録する。
logical file sizeや仮想disk容量を使用量と数えていない。root filesystem全体の利用は並行して
変化し得るため、dfの差分だけを回収量としていない。

元ISO・対応ソース・受入記録は保持した。旧buildのmanifest/record等は削除前にguestの
`/build/retired-build-records-20260912.tar.xz`へ保存し、hashを`builder-cleanup.log`に記録した。
導入済みpackage databaseのhashは削除前後で不変。guest停止結果は`builder-exit.json`。
変更後のbuilderへ過去のVM試験全体の同一性を主張しない。今回も不変runtimeの再認定はしない。

再発防止としてtest-suiteは全6項目が終了した後だけ、所有する導入disk2個を削除する。
`--retain-disks`指定時と失敗時は保持する。全candidateを先に通常file/所有者/単一linkとして検査し、
POSIX write lockを保持してQEMU稼働中の削除を拒否する。symlinkやentry置換も拒否する。
ログ・ISOは消さず、部分的なcleanup失敗もreportへ残す。

20件のimage工具試験が成功。追加ケースは成功時の限定削除、2番目のsymlink/実別process lock
による削除前拒否、全suiteの順序・明示保持・失敗保持。さらに実QEMUのimage lockとの競合と
停止後の削除を確認した。模擬suiteは新しいISOの起動受入として数えない。
これは開発storageの改善であり、本番供給/同意/全DEB効果/起動切替の完成ではない。
