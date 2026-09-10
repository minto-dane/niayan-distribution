# 元DEBからの論理ファイル所有権

`Pkg_Payload_Ownership.Check`は、封印済みcatalogとpayload indexの全pathについて、
明示された採用claimを検査する。元DEBのcontrolにある関係と元payloadの属性を使い、
別のinstalled DBや包括的な上書き許可を追加しない。

共有directoryは数値UID/GID、mode、ACL、xattr、flagsが一致する場合に許す。
同名・同version・異なるarchitectureの全`Multi-Arch: same` instanceは、解決したinodeの
kind、内容hashと長さ、link先、device番号と同じ属性が一致する場合に共有できる。
比較では時刻と象徴的な所有者名を除くが、選択した元tarのそれらの情報は消さない。
これはNiaの属性一致条件であり、異なる管理者設定の自動統合を意味しない。

その他の競合は、採用packageの直接の`Replaces`が失う側の実package名、version、
architectureを満たす場合に限る。逆向き・推移的な関係や`Provides`の仮想名を使わない。
無修飾と`:any`は全architectureを対象とし、`:all`および対象の`Architecture: all`は
明示されたnative architectureへ対応付ける。依存・Breaks・適用順序の検査は既存の
final-set/transition検査で別途行う。単独の所有権成功を依存解決成功にしない。

参照した一次資料は[Debian PolicyのReplaces](https://www.debian.org/doc/debian-policy/ch-relationships.html#overwriting-files-and-replacing-packages-replaces)
と[Multi-Arch](https://www.debian.org/doc/debian-policy/ch-controlfields.html#multi-arch)。
architecture修飾は、受入ISOの対応ソース収集で保持したdpkg 1.22.22の
`src/main/archives.c`と`src/main/depcon.c`も確認した。上流コードは改変・複製していない。

## 世代への接続

`Pkg_Root_Archive.Verify_Ownership`は既存NIAROOT1のcatalog/closure、完全な選択、
元span、tarの検証に論理所有権検査を加える。NIAGEN05の保持検査は、この入口を必須とする。
native architectureは同じcatalog/closureに束縛された保持intentから読み、外部の未束縛値を
世代の検査へ差し込まない。既存のstaging、公開、予約受渡し後のguard、記録済み復旧、
現在世代の観測で適用される。NIAROOT1/NIAGEN05のwire形式は変えない。

成功の診断digestは`NIAPOWN1`、catalog fingerprint、payload fingerprint、native名の
長さとbytes、選択数、順序付きclaim番号のSHA-256である。整数は8 byte big endian。
診断digestを認可tokenや第二の永続正本にしない。失敗出力はzero、理由とclaim位置は
言語に依存しないenum/数値で返す。表示層が翻訳を担当する。

## 適用範囲

この検査は選択集合内の論理所有権を扱う。管理者のconffile変更、旧世代からの削除と移管の
実effect、diversions、alternatives、maintainer script、trigger、device生成、特権展開と
実root状態は別の契約・実装を必要とする。SDKのUID0拒否、有限期限、既存writer予約を維持する。

小さい人工DEBで方向・実名・version・architecture、共有内容/属性、期限と選択範囲を検査する。
root fixtureのcontrolには必要な直接`Replaces`を明記した。これは自作試験入力の修正であり、
配布元DEBやその依存の書換えではない。root組立て・stagingと既存公開/復旧の変更境界を検証し、
同じ入力の全体試験・証明・性能測定を繰り返さない。本番provider、全DEB効果とサービス接続、
実展開/起動切替、完全置換ISOは引き続き必要である。
