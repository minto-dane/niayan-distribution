# 原本制御項目と識別情報の検証

対象source subjectと結果は[report.json](report.json)。
固定Debian 13コンテナで全ソース、4アプリ、17 Ada mainを検査した。
新しい読取器109 assertions、制御アーカイブ229、envelope764 assertionsが成功した。
35合成制御DEBは必須Maintainerを追加して再生成し、生成物の再照合も成功した。

異なるパス・入力mtime・TZの独立二ビルドで21実行ファイルの全byte列が一致した。
[392入力](pkgcore-inputs.json)を両ビルドとcheckoutへ照合した。
通常21 ELFのPIE・非実行stack・RELRO・即時binding・非RWX LOADを検査した。
別root contextで新しい元DEB観測SDKの入口拒否を確認した。
新Ada runtimeはSPARK対象外。既存7repoのproof入力集合は不変である。

最終binaryで元DEB13個の識別情報と153項目名を独立のread-only
`dpkg-deb --field`とraw CASに照合した。7個は保存済みcomponent DEB、6個は上流cache原本。
二つの輸送filenameは既存内部path規則に合わせた別名を使う。元filenameとbyte hashは
[入力](original-media-inputs.json)に保持する。供給認証やインストール実行の検証ではない。
`dpkg-deb`は検証コンテナだけのoracleであり、本番依存や内部backendには追加していない。

初回通し試験のスタック不足は大きな中間recordをheapへ移して修正した。
診断用の一時コピーと失敗ログはattemptsへ区別し、資源上限は変更していない。
重い工程は一つずつ、3 GiB・swapなし・CPU 1コア分・128プロセスの制限で実行した。
ソース24工程は同じ前後subjectで成功した。

項目位置はprivate型で原本hashへ束縛し、未知項目を削除しない。
識別情報の検査は依存関係・任意項目全体・mailbox本人確認・全DEB効果の認定ではない。
data.tar、稼働catalogと認可、実boot、完全置換ISO、全言語翻訳は未完。
[実装範囲](../../../native/deb-metadata.ja.md)を参照。
