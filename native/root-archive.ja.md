# 元DEBからのrootアーカイブ組立て

`Pkg_Root_Archive`は、保持閉包を検査した選択catalogから、実payloadを一つのtarと
NIAROOT1 manifestへ組み立てる内部SDKである。旧file-planが表現できないhardlink、
device、FIFO、負の時刻、PAX/GNU属性を切り捨てず、元tarのレコードをそのままコピーする。
本番rootへの展開、maintainer scriptの効果、公開認可、起動切替はこのAPIの仕事に含めない。

## 採用元と順序

呼出側は、payload indexの全canonical pathについて一つのclaim番号をpath順に渡す。
共有directoryを含めて採用元を明示する。package入力順による暗黙の上書きはない。
空pathのrootと全祖先pathは選択済みdirectoryでなければならない。全pathの網羅と順序、
hardlinkの直接参照先が同じ元DEBから選ばれていることを検査する。

出力はdirectory群、その他の順で、各群は元DEB hashと元tar内位置を基準にする。
hardlinkは直接参照先を先に出力する。元DEBの検査済みgraphを保持し、循環検査は反復処理で行う。
directoryの親子順はpackageをまたいで保証しない。将来の展開器はdirectoryの一時作成と
最終属性の適用を分離し、子の作成が親の最終属性を壊さないようにする必要がある。

各レコードのlocal PAX/GNU拡張header、通常header、bodyとpaddingを元tarからコピーする。
全体末尾だけを二つのzero blockに揃える。保持されたctime/creationtimeの情報が
物理inodeへ復元できるとは主張しない。属性を実現できない展開先の扱いは別の効果契約で決める。

## 保持形式

整数はbig endian。claim番号はpayload indexの1起点番号で、呼出側配列の添字に依存しない。

| 0起点offset | bytes | 内容 |
| --- | --- | --- |
| 0 | 8 | NIAROOT1 |
| 8 | 32 | 選択catalog hash |
| 40 | 32 | catalog保持閉包 hash |
| 72 | 32 | payload index fingerprint |
| 104 | 32 | 組立てたroot tar hash |
| 136 | 8 | root tar長 |
| 144 | 8 | 選択claim件数 |
| 152 | 件数×8 | canonical path順の選択claim番号 |

最大524,288 path、4,096元package。各元tarの131,072 entry上限とCASの8 GiB上限は維持する。
root tarも呼出側の有限容量上限と8 GiB以内に制限する。全量OSがこの上限へ収まるとの認定ではない。
出力全体をRAMへ置かず、span情報を有界に保持し、hash算出とCAS書込みの二つのpassでstreamする。
同一passの連続した元tarは同じFDを使用する。各openで元objectをhash検査し、scan時と
各FDを開いてから閉じるまでの前後に観測したfile identityを照合する。有限BOOTTIME期限と既存CAS予約を必要とする。

`Verify`はmanifestと既存root tarを読み、その長さとhashを検査してから原本から再組立てする。
必須の保持入力が欠けていたら再生成前に拒否する。再組立て結果は全manifest bytesと一致させる。
UID0を拒否し、失敗時の出力digestはzeroにする。失敗した呼出しでも未参照の完全なCAS objectが
残り得る。非成功を「書込みなし」と解釈しない。

## 本番接続で残ること

構造が正しい選択でも、所有権変更が認可済みとは限らない。Replaces、共有所有、conffile、
alternatives/diversions等の意味とsite policyに基づく採用決定を、供給・効果・公開計画へ
束縛するproviderが必要である。manifest単独を認可や導入済みDBとして利用しない。

NIAGEN05を通して既存の世代pin・公開/復旧へ接続した。[root世代](root-generation.ja.md)を参照。
全世代の保持・GC、特権分離された展開器、
効果の実行と復旧、実サービス・root/boot接続を実装してから完全置換ISOの受入へ進む。
今回の検証対象は人工DEBの実payload組立てであり、ディストリビューション完成ではない。

通常のcomponent CIと統合runnerに専用Ada driverを登録し、Python tarfileによる独立読取で
元DEBの選択span・全属性・path網羅・hardlink順とNIAROOT1の選択番号を照合する。
欠損や復元は私有CASに限定する。変更のない試験・証明・既存カオスcampaignを重複実行しない。
