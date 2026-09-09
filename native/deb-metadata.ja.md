# 元DEBの制御項目と識別情報を読むnative SDK

`Pkg_Deb_Fields`は制御ファイルのprivateな位置索引を作り、原本hashと対応した値を返す。
`Pkg_Deb_Metadata.Inspect`は元DEB → ar envelope → 圧縮制御メンバー → raw control →
位置索引と識別情報を、既存のnative SDKとCASで検査する。公開コマンドや導入済みDBは追加しない。
InspectはUID 0を拒否する。メモリ内の純粋な項目読取は権限を変更しない。

## 項目の規則

単一binary stanzaを必要とし、項目名の大文字小文字を区別しない。
印刷可能ASCIIから空白とcolonを除き、先頭の`#`と`-`を禁止する項目名規則を使う。
未知の項目名や本文は削らず、原本に束縛したまま取り出せる。
重複名、空値、orphan continuation、別stanza、source用comment、不正UTF-8と制御byteを拒否する。
UTF-8は過長符号化・surrogate・上限超過・途中切断も検査し、表示localeで変換しない。
LFとCRLFのframingを扱い、裸のCRは拒否する。外側の空行は許容する。
根拠は[Debian Policyの制御項目](https://www.debian.org/doc/debian-policy/ch-controlfields.html)。

上限はraw control 16 MiB、1行65,536 byte、256項目、項目名4,096 byte。
項目位置はAdaのprivate型に保持し、値を読むときにraw全体のhashとサイズを再照合する。
呼出側が返却recordのoffsetを直接変更するAPIは用意しない。

`Read_Value`は四つの扱いを明示する。

- `Raw_Field`: colon直後から最後の行末までの原本byte列。
- `Simple`: 一行だけを許容し、左右の水平空白を除く。折返しは拒否する。
- `Folded`: 空白・改行を一つの空白へまとめる。呼出側がそのfieldで許可されるか判断する。
- `Multiline`: 第一行をtrimし、続く行の先頭の一つのindentを除く。残る字下げ・改行・`.`を保持する。

出力bufferが小さければ失敗し、値の先頭だけを成功として返さない。
Raw_Field以外は原本の改変ではなく、明示した読取り表現である。
Read_Valueは関係項目の適合性を判定しない。後続のバイナリ関係項目の意味検査では
Simpleを要求し、Foldedで改行の違反を消してはならない。関係項目は[Policy第7章](https://www.debian.org/doc/debian-policy/ch-relationships.html)を別途満たす必要がある。

## 識別情報と境界

`Check_Identity`はPackage、Version、Architecture、Maintainer、Descriptionの存在と
必要なlayoutを検査する。Package名と既存のnative DEB版検査を用い、Sourceの任意版を解釈する。
Source省略時にはpackage名・版を用い、Sourceに名前だけがあればbinary版を用いる。
Multi-Archの四値、Essential/Protectedのyes/no、非負のInstalled-Sizeを扱う。
Architecture: allとMulti-Arch: sameの組は拒否する。

Architectureはlabel構文の観測であり、稼働platformが対応するという判定ではない。
Maintainerの検査も本人確認や完全なmailbox文法の検証ではない。
Installed-Sizeは宣言値であり、payloadの実測やディスク予約を置き換えない。
採用11関係fieldの構文は[関係読取器](deb-relations.ja.md)で追加検査する。
任意field全体、依存の充足・phase・所有権、保守scriptとtriggerの意味検査は未完。
したがって識別情報が得られても、単独では実行許可・全package適合・認証成功にならない。

## 資源と検証

原本経路にはboottime期限と外側の時間・資源制限が必要である。
大きな中間inventoryと観測recordはheapへ確保し、成功・失敗時に解放する。
文字列・索引は有界であり、stack上へ全段階の大きなrecordを重ねない。
新runtimeはSPARKの対象外で、独立実行検査が必要である。

登録試験は`pkgcore/tests/run_deb_metadata_tests.adb`。
合成制御fixtureへ必須Maintainerを追加し、既存の圧縮破損試験の拒否条件は維持する。
元DEB13個の実観測を`dpkg-deb --field`のread-only出力と照合する。
この工具は検証用コンテナのoracleであり、稼働Niaの依存や内部backendではない。
証跡は`evidence/native-transition/deb-metadata-01/`。
