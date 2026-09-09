# 非公開世代の組立てSDKの検証

対象source subjectは
`4532df17d6c523bc12a9a6ac34c83fe9114b14e46cdc7d443d94fee0f474cbf0`。
対象・入力hash・結果の正本は[report.json](report.json)。

既存ビルドを持ち込まない独立したpkgcore checkoutで、固定Debian開発コンテナの
`make compile-all build test`が終了値0となった。全13本のAda test mainが成功し、
新規stage試験は1,170 assertionsを通過した。306個のコンパイル・試験入力は
現行checkoutと実行checkoutでhashが一致する。CIのroot拒否stepはこのビルド後に
追加し、別のrootコンテナで実試験した。GitHub上での実行は未実施。

1,054項目を2分割し、単一directoryの1,050ファイルを全件検査した。
分割をまたぐ重複・親欠落・別catalog/transaction・禁止パス・逃避symlink、
途中適用とcommitの認可取消、確定前後の再開、再実行、余分な項目、同属性の内容変更、
private modeの喪失、同時writer、lock欠落、古いjournalの欠落と部分末尾を検査した。
人工の永続prefixを作る試験であり、実電源断やfsync/容量不足の故障注入ではない。

root専用コンテナでは有効な人工入力を使って3つのSDK関数の拒否を確認した。
fixture準備・形式検査を含む1,099 assertions。再起動前にも成功markerがあるが、
プロセスの終了記録を回収できなかったため再実行し、終了値0を確認した。
ソースmountはread-only、ネットワークは無効。全実行の外側でメモリ3 GiB、swap 0、
CPU 1コア分、128プロセスのkernel制限を読み戻した。

再起動後のソース統合検査24工程も終了値0で、前後のsubjectが一致した。
これは開発環境での検査であり、固定コンテナでのAda実行とは区別する。
サンドボックスがuser busを拒否した記録を保持し、承認された制限付きscopeで再実行した。

全7コンポーネントの既存proof入力をhashとファイル集合で再照合した。
数学的入力は不変のため同じ証明を再実行していない。新規runtime/FFIはSPARK証明の対象外。
最初のコンパイルエラーと、人工journal frameの添字修正前の失敗も`attempts/`へ保持した。

本番認可adapter、catalogの意味、全DEB効果と特権属性、単一root/catalog公開、
新ISO、実電源断、全言語翻訳、TUI/GUI、公開運用は未完。
SDKの物理検査結果を実行許可や完全置換の受入へ読み替えない。
