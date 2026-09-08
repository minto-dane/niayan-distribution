# 配布工程後のソース検査

2026-09-08。資源制限下で`run-engineering-checks.py --mode source`を実行し、全24工程が成功した。実行前後のsource subjectは`35f0072871a19fb269111dc4727428968b9bb0c3418a63a31840a4fbaa273acf`で一致した。結果の範囲はソース・参照試験・契約・構文と文書リンクであり、Ada全ビルドやSPARK証明の再実行ではない。7コンポーネントのcommitと数学的入力は不変で、以前の実ビルド・証明結果は元の対象へ束縛したまま維持する。

[report](report.json)と[集計](summary.json)を保存した。ログは元のバイト列をgzip mtime 0で圧縮し、reportのlog_sha256は展開後の内容に対応する。source subjectはevidenceを除く実ファイルの内容で、Gitのcommit hashとは異なる。

Python試験は555件の登録を走査し、通常のこのcontextで544件が成功した。root専用1件と私有D-Bus10件はskipであり、今回成功した件数へ含めない。これらの別contextでの以前の受入結果はworkspaceのSTATUSに記録している。配布工具の16件は別のimage-checkログにある。
