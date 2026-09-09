# 全原本の所有権主張を保持する索引

`Pkg_Payload_Index`は、完全な`Pkg_Deb_Payload.Inventory`から原本ごとのclaimを
集める内部SDKである。導入済みcatalog、所有者選択器、ファイル実行器ではない。
[設計判断](../../assurance/docs/engineering/adr/ADR-0067.ja.md)を参照。

## 呼出し

`Add`で原本inventoryを追加し、`Seal`で全体の順序とfingerprintを確定する。
原本は完全な読取結果をコピーするため、元inventoryをClearしても索引は変わらない。
全体seal前の件数・hash・読取には候補を公開しない。同一原本の二重追加を拒否する。
`Add`と`Seal`の失敗は候補全体をClearし、部分的に残ったownerを採用しない。
sealed索引への追加も拒否してClearする。Clearは繰り返し可能である。

最大4096原本・524288 claim・名前合計256MiB。元payloadの個別上限も維持する。
UID0を拒否し、追加・sort・hash中にdeadlineを検査する。外側の資源制限も必要である。
この索引はCAS objectのpinや現在の認可を保証しない。
Sealが保証するのは、呼出側が渡した原本集合についての完全な索引である。
呼出側は`Read_Package`の全原本一覧を、認可・依存解決で選択された正確な集合と
過不足なく照合しなければならない。最初から渡されなかった原本の欠落は、この層では検出しない。

`Read_Package`は原本digest順に、`Read_Claim`はbyte path・原本digest順に返す。
`Read_Claim`は原本header、`Read_Inode`はhardlinkが指す同じ原本内のregular headerを返す。
原本digestとsource ordinalを組にし、別ownerの同名pathへinodeを付け替えない。
`Read_Inode`が返すのは参照先regularの原本headerであり、最終filesystemの属性ではない。
hardlink header独自のmode等も`Read_Claim`に残る。属性を適用する順序と効果の検査は別に必要である。

`Inspect_Path`は全claimの範囲、directoryのみか、inode属性が同じか、
直近parentの宣言がないか、非directory祖先があるかを返す。
属性比較はnumeric owner、全時刻、内容・属性blob、flags、link bytes等を使う。
原本内inode ordinalとsymbolic owner名は物理inode属性の比較から除くが、原本claimとhashには残す。
同一属性でも共有の許可ではない。directoryのmtime等が異なっていてもclaimを消さない。
`Same_Inode_Attributes`は参照先headerへ展開した保持属性の比較で、未実装の適用処理を
実行した結果の一致ではない。
rootは空のbyte pathとして問い合わせる。暗黙のroot/parentは作らない。

非directory祖先には世代内aliasの解決が必要な場合もあり、この観測だけで
導入の可否を決めない。package identity/版/architecture、Replaces、Multi-Arch、構成と
効果契約に基づく実効所有権とnamespace解決はcatalog側で独立に行う必要がある。

## Canonical fingerprint v1

これは永続DB形式ではなく、候補索引の全情報を束縛するhashの入力形式である。
整数は8 byte big-endian、digestは32 raw bytes、文字列はbyte長u64とそのraw bytes。
時刻はPresentを0/1のu64、secondsを64bit二の補数、nanosecondsをu64で記録する。
Unicode正規化やlocale変換を行わない。

1. 文字列`NIAPIDX1`、原本数、claim数。
2. 原本digest順に、原本digest・tar digest・entry数。
3. byte path・原本digest順に各claimを次の順で記録する。

各claim: path文字列、原本digest、1起点source ordinal、link・user・groupの各文字列、
kind、mode、UID、GID、device major/minor、modified/accessed/changed/createdの4時刻、
archive/content size、content/xattr/ACLの3 digest、set/clear flags、原本内inode ordinal。
kind番号はregular0、directory1、symlink2、hardlink3、character4、block5、FIFO6。
空payloadの原本も必ず2の一覧に残す。列挙型の変更等で意味を変える場合は版を変える。
