# 媒体コマンドの検証

対象source subjectは
`b2b9795aa6de090627c3e742be5dfabc9f408015a5430394dea3e0d871200f53`。
実行結果は[report.json](report.json)、固定コンテナへ渡した189入力は[tested-inputs.json](tested-inputs.json)。
全入力が最終checkoutと一致することを照合した。

固定Debianコンテナの`make image-check`が終了値0となり、native 122・hardening 4・image 16、
計142試験が省略なしで成功した。Python compileallとshell構文検査も完了した。
媒体14試験は実公開コマンド、原本不変、再現性、同一索引のinode保持、古い索引と再作成、
Unicode・epochの復号、読取途中の変化、入力上限、リンク・FIFO、directory予約、
書込み・fsync・rename失敗を含む。rename後の親fsync失敗では完全な新版が見える場合も検査する。
これらは模擬したIO失敗であり、実電源断試験ではない。

保存済みの7コンポーネントの実DEBを、基準ISOの保存済みhashへ照合して使い捨て媒体へコピーした。
[原本の照合](original-media-inputs.json)、[実行結果](real-media-result.json)、
[公開コマンドによる検証手順](validate_real_media.py)を保存している。
inutocの初回・同一内容の再実行、installp -l、installp -Lとgeninstall -Lを実行し、
7原本のSHA-256保持、索引再現性、機械処理出力のlocale非依存を確認した。
これは古い基準ISO用の実DEBの媒体検査で、現行コンポーネントの再ビルドや導入試験ではない。

英語原文119件と既存7翻訳catalogの整合性検査も成功した。
[全言語gate](language-coverage.json)は未翻訳が残るため想定どおり終了値1となった。
訳文の第三者レビューとGUI・入力の受入は未実施。

ソース統合検査24工程が成功し、前後のsubjectが一致した。
全7repoの既存proof入力集合・hashは不変で、形式証明は再実行していない。
媒体Pythonを形式証明済みとは扱わない。
各重い実行は一つずつ、メモリ3 GiB・swap 0・CPU 1コア分・128プロセスの制限を読み戻した。
コンテナはUID 1000、ネットワークなしで実行した。

実装台帳へ媒体操作の状態名を追加した後、入口照合試験がその名前を認識せず失敗した。
追加した二つの状態を試験へ登録し、台帳・HELP・実ファイルの完全一致検査を維持して再実行した。
失敗ログは`attempts/registry-state-mismatch.log`に保持した。

媒体索引は供給認証・導入済みDB・実行許可を持たない。
稼働更新・全DEB効果・実boot切替・復旧・完全置換ISOと完全な応答互換性は未完である。
