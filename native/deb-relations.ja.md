# nativeのbinary関係項目

`Pkg_Deb_Relations`は制御項目の値をprivateな有界式へ読み、個々のatomを返す。
Depends、Pre-Depends、Recommends、Suggests、Enhances、Breaks、Conflicts、Replaces、
Provides、Built-Using、Static-Built-Usingの11項目を扱う。
名前・版・architecture labelとgroup順序を保持し、原本を修正しない。

## 文法と原本の対応

選択肢を許す4項目でのみ`|`を受け、5種類の現行版演算子を既存のnative版検査へ接続する。
Providesは任意の等号版、ソース保持2項目は必須の等号版と無修飾名を要求する。
Providesにもarchitecture指定を保持する。根拠は[Debian 13 deb-control](https://manpages.debian.org/trixie/dpkg-dev/deb-control.5.en.html)。

binary関係項目はSimpleとして読み、改行を正規化して違反を隠さない。
source用のarchitecture制限やbuild profile、未置換変数、古い単独不等号は拒否する。
規則は[Debian Policyの関係項目](https://www.debian.org/doc/debian-policy/ch-relationships.html)を参照する。

`Read_Field`は項目が不在でもraw control全体とprivateな項目索引のhashを照合する。
`Parse`単独の結果はcontrol hashを持たない。`Validate_All`は11項目を順に検査する。
元DEBの`Pkg_Deb_Metadata.Inspect`にも接続し、不正関係項目を含む原本は観測成功にしない。
上限は1項目65,536 byte・1,024 atoms・名前/label4,096 byte、版は既存512 byteである。
部分的な式や切り詰めた値を成功として返さない。

## 意味検査と実行の境界

architectureはliteral labelであり、対応CPUの認定やwildcard展開ではない。
例えば`arm64`をamd64に置換しない。unqualifiedの意味も関係項目の種類で異なるため、
項目種別を失ったatomだけで充足判定してはならない。
式を取得しても、候補集合の充足、Pre-Dependsの過去版、cycle、共存、
Breaks/Conflictsの段階、Replacesの所有権移管、ソース保持の履行は未検査である。
`Pkg_Deb_Semantics`の既存型に無理な拡張や意味の縮約をしていない。

新runtimeはSPARK対象外。CPU時間を含む外側の資源制限が必要である。
構文試験と原本比較の証跡は`evidence/native-transition/deb-relations-01/`へ保存する。
稼働DB・公開コマンド・特権backendは追加しない。
