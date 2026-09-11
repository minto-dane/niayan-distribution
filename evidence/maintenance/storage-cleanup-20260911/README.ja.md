# 2026-09-11 開発ストレージ整理

利用者の明示的な削除依頼に従い、終了済みの使い捨てVM差分と旧ISO、過去の生成build cacheを削除した。
48 image file、105 build directory。空き容量の増加は13,053,005,824 bytes（約12.16 GiB）。
最新の受入ISO 09、二つの受入installed VM、builder/baseとそのbacking chain、対応source、
ソースtree、署名付き原本、全sealed evidence、現在のnative-configured-publication-01は保持した。

最初の実行はDistroboxからhost PID 1のFD列挙を拒否され、削除前に停止した。
次の実行ではその制約を記録し、見えるFDの使用状況と全QEMUの停止を確認した。
完全なhost FD可視性は主張しない。削除対象は明示的に列挙した終了済み私有試験出力に限定した。
保持する4 qcow2のqemu-img infoも記録し、削除対象へのbacking参照がないことを確認した。
全削除は3 GiB/swap0/CPU1/pids128のscopeで順次行った。

過去labの実行をやり直す場合、削除済みcompiler cacheと使い捨てVM差分を保存済みsource/recipeから
再構築する必要がある。過去のhash付きログは再実行済みと変更していない。
