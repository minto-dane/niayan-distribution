# native binary関係項目の検証

対象source subjectと結果は[report.json](report.json)。
固定Debian 13コンテナの全ソース、4アプリ、18 Ada mainを検査した。
関係項目176 assertions、原本メタデータ117、制御アーカイブ229、envelope764 assertionsが成功。
正常な関係項目と、構造は正常だがProvides条件が不正なDEBを追加し、
37合成制御DEBの再生成一致を検査した。拒否条件は弱めていない。

元DEBからの通し観測には11関係項目の構文検査が接続されている。
最終実行ファイルで保存済み13元DEBの153項目と識別情報をread-only `dpkg-deb --field`とCASへ照合した。
7個はコンポーネント原本、6個は上流cache原本。二つの輸送名の別名は[入力](original-media-inputs.json)に明記する。
この比較工具は検証コンテナだけのoracleであり、稼働backendや新たな供給認証ではない。

別に、ISO 09から保存したstatusのhashを既存証跡へ照合し、2,239パッケージの
4,388関係項目・20,234 atomsをnative読取器と既存の独立Python参照へ比較した。
項目・group順序・名前・architecture指定・版演算子・版が一致した。
これはstatus由来の関係値の比較で、2,239個の元DEBの再検証ではない。
Python参照の限定profileを超えるProvidesのarchitecture指定等はnativeの明示試験で別途検査する。
入力値と参照source hashは[corpus-inputs.json](corpus-inputs.json)、[結果](corpus-results.json)へ保持する。

二つの新規作業パス・入力mtime・TZによる22実行ファイルの全byte列一致を確認する。
[397入力](pkgcore-inputs.json)は両ビルドとcheckoutへ照合する。
引数なし試験の生成runnerに残っていた末尾空白は共有generatorで修正した。
他6repoのrunner差分は空白だけと照合し、pkgcoreは修正runnerで18試験を再実行する。
compile/link入力は不変で、修正前後の入力一覧を区別して保存する。
通常22 ELFのPIE・非実行stack・RELRO・即時binding・非RWX LOADを検査する。
元DEB観測SDKのUID 0拒否も別root contextで検査する。
ソース24工程の前後subjectは同じである。既存全7repoのproof入力は不変であり、
新しいAda runtimeをSPARK証明済みとは扱わない。
重い工程は一つずつ、3 GiB・swapなし・CPU 1コア分・128プロセスで実行する。

構文と順序を保持しても、依存集合の充足、architecture共存、各phaseの効果、
ソース保持の履行、所有権移管、稼働catalog・認可、実root/boot、完全置換ISO、全言語翻訳は未完である。
[実装境界](../../../native/deb-relations.ja.md)を参照する。
