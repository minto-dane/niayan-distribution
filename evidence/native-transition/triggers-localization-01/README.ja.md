# トリガー宣言と追加翻訳の検証

対象source subjectは
`ef6012e2bbd64da55bc9b012abc15e80acb5b4b9d83564c0d32e36d836365fef`。
対象入力と結果は[report.json](report.json)、全入力hashは[source-inputs.json](source-inputs.json)。

固定Debianコンテナの使い捨てコピーで`make image-check`が終了値0となり、
native 108、hardening 4、image 16の計128試験とPython・shell構文検査が成功した。
別のGPGを含む固定開発コンテナで配布工具145試験も省略なしで成功した。
トリガー試験11件は9通りのawait条件、旧新宣言、6段階、ファイルprefix、自己待機の除外、
配送の集約、入力上限、原本DEBから候補catalogまでの接続を含む。
コンテナIDと試験別入力一覧を保存し、実装・翻訳・試験の現行hashを照合している。
使い捨てコピーの後に変わったacceptance.jsonは、この証跡と翻訳状況を参照する台帳だけである。

[元ISOの宣言照合](trigger-corpus.json)では1,186ファイルの内容とサイズを過去のinventoryへ照合し、
1,224個の正規化された宣言を得た。parserのhashと元inventoryのhashも記録した。
handlerを実行した記録ではない。

ドイツ語・スペイン語・フランス語・韓国語・中国語簡体字・繁体字を追加した。
英語原文115メッセージと各115件の7翻訳catalogを検査し、公開12コマンドの構文、
エラーの出力先と終了値、動的な識別子が表示言語で変わらないことを確認した。
[全言語検査](language-coverage.json)は想定どおり終了値1となった。
509 glibc locale/encoding組と78 installer選択肢の計587行のうち、95行が訳文を使用、
39行が英語原文、453行が英語fallbackとなる。行数は言語数ではない。
282の異なるlocale対象が未翻訳で、第三者の訳文レビューとGUI・入力の受入も未実施。

ソース統合検査24工程が成功し、前後のsubjectが一致した。
全7コンポーネントの既存proof入力は集合とhashが不変で、証明は再実行していない。
今回のPython実装と訳文を形式証明済みとは扱わない。
重い検査は一つずつ、メモリ3 GiB・swap 0・CPU 1コア分・128プロセスの制限下で実行した。

最初の読み取り専用コピーではnative 108試験の後、compileallのキャッシュ書込みが失敗した。
配布工具試験では独立checkoutに対する既存試験の親パス仮定が失敗した。
書込み可能な使い捨てコピーとリポジトリ内相対パスで再検査した。失敗ログも`attempts/`に保持する。

実handler実行とnative lifecycle/WAL、全DEB効果、稼働管理器への接続、本番認可、
実mount/boot切替・電源断復旧・完全置換ISO・全言語の受入は未完である。
