# 多言語CLIとDebian全言語対象の検証

固定Debian 13コンテナでnative 107件、hardening 4件、image 16件が成功した。
同じCLIの署名付きHTTPS取得は、別の使い捨てrootコンテナで英語・日本語を含む
6項目を試験する。各実行はメモリ3 GiB・swapなし・CPU 1コア・128プロセスの制限下。
実行結果と対象入力ハッシュの正本はreport.jsonと個別ログに保存する。

gettextの115メッセージ、文脈付き訳語、名前付き引数、複数形、言語優先順、
欠落・破損時のfallback、日本語・RTL文字・ZWNJ/ZWJ・ASCII端末、並行表示を検査した。
実コマンドで終了値とstdout/stderr、作成物の元DEBバイト列を照合した。
localeの変種を保持し、固定したglibcの全509組とinstallerの78選択肢を列挙して照合した。

言語の選択・検索を扱えることと、その言語に翻訳済みであることは別である。
英語原文と日本語訳以外は未完であり、全言語release gateは期待どおり終了値1となる。
language-coverage.jsonに未完対象を省略せず記録した。この失敗を通常試験の成功で
置き換えない。フォント・shaping・入力method・TUI/GUI・読み上げ・参照応答への完全適合、
稼働catalog・適用・削除・新ISOは未受入。Adaのソースと数学的入力は変更していない。
