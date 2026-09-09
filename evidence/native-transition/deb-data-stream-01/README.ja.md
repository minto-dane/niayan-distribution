# 元DEB data streamの検証

対象source subjectと結果は[report.json](report.json)。
固定Debian 13コンテナで全ソース、4アプリ、19 Ada mainを検査した。
新stream経路389 assertions、関係176、メタデータ117、制御229、envelope764 assertionsが成功した。
43 fixtureファイルには30合成DEBがあり、再生成した全byte列とmanifestが一致した。
6 codecについて1 byteから64 KiBまでの入力・出力分割、空stream、ちょうどの展開上限、
CRC等の不正・切断・連結・後続byte、失敗/完了後の再使用、root拒否を検査した。

最終native実行ファイルで保存済み13元DEBと大型の合成DEBを検査した。
独立ar読取で圧縮メンバーのhashを、read-only `dpkg-deb --fsys-tarfile`で全展開byteのhash・サイズを比較し、
CASへ保存した全byte列も一致した。計14入力、展開計166,123,520 byteである。
このDebian工具はビルド時のoracleであり、稼働backendには追加していない。
13原本の輸送別名2個と元filenameは[入力](original-media-inputs.json)に保持する。

[大型入力](large-input.json)は96 MiBの通常fileを含むtarで、展開後100,669,440 byte。
全展開物をメモリに作らずにfixtureを生成し、元DEBと展開物のhashを記録した。
各native probeは新しい計測processから起動し、Linuxの子process最大RSSを採取した。
大型probeの最大RSSは14,660 KiB、14件全体の最大は14,752 KiBであった。
この測定は当該入力・当該環境の結果で、全形式のメモリ不存在証明ではない。

異なる作業パス・入力mtime・TZの独立二ビルドで23実行ファイルの全byte列一致を確認する。
[446入力](pkgcore-inputs.json)は両ビルド・sanitizer用コピー・checkoutへ照合する。
23 ELFのPIE・非実行stack・RELRO・即時binding・非RWX LOADも検査する。
C境界をASan/UBSanで計測して389 assertionsを実行する。Adaと上流libraryは非計測、
leak検査は無効である。設定は[commands.json](commands.json)に区別する。
最終試験の追加時にAda整数演算子の可視性不足を検出して修正した。初回失敗ログも保存する。
sanitizerの初回実行はCAS用fixture directoryのmode不備で拒否されたため、
検証directoryを0700にして再実行する。保存機構のprivate条件は変更していない。

直接のlibbz2-dev依存を開発と共有CIに明記した。
構築済み固定imageにはlibbz2-dev 1.0.8-6が既にあり、今回はimageを再構築していない。
全7repoの既存proof入力は不変。新Ada/C runtimeはSPARK対象外である。
重い工程は一つずつ、3 GiB・swapなし・CPU 1コア分・128プロセスで実行する。
ソース24工程は同じ前後subjectで検査する。

保存したbyteはまだopaqueであり、tar entryの意味・path・所有権・属性や実抽出の検証ではない。
全DEB効果、稼働catalogと認可、実root/boot、完全置換ISO、全言語翻訳は引き続き未完。
[実装境界](../../../native/deb-data-stream.ja.md)を参照する。
