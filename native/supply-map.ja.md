# 更新に必要な原本を網羅する供給記録

`Pkg_Supply_Map`は候補catalogの原本集合から基準catalogの原本集合を引き、必要な供給記録と
完全一致することをnativeで検査する。名前・versionの一致ではなく元DEB bytesのhashで比較する。
初期構築では全原本、通常更新では新規原本だけを要求する。不変原本の再掲載や古い供給記録の
期限更新は要求しない。削除だけの更新は供給記録0件になり得る。

## 形式

NIASMAP1は次の正規CAS原本で、すべての整数はbig endianである。

| 0起点offset | bytes | 内容 |
| --- | --- | --- |
| 0 | 8 | `NIASMAP1` |
| 8 | 16 | root identity |
| 24 | 32 | 基準descriptor hash、初期構築のみzero |
| 56 | 32 | 基準catalog closure hash、初期構築のみzero |
| 88 | 32 | 候補catalog hash |
| 120 | 32 | 候補catalog closure hash |
| 152 | 8 | 新規原本件数 |
| 160 | 件数×96 | 元DEB hash、raw control hash、NIASUP01 hashの組 |

件数は既存catalog上限4096まで。行は元DEB hashの厳密な昇順で、重複・zero・余剰・切断を拒否する。
基準と候補の取り違え、初期構築への変更は異なるmapとなり、Verifyの期待contextと一致しない。
同じ入力は同じmap addressになる。mapは自分自身を参照しない。
Ada配列の開始添字はmapのbytesへ影響しない。消費した件数を相対位置で数え、
型の最大添字に置かれた1件の配列でも終端の加算overflowを起こさない。

## 検査

Prepare/Verifyは最大256件の独立authorityを受け取り、scopeの重複を拒否する。記録自身の鍵は採用しない。
全供給記録の全参照原本を先に開き直し、欠損を派生cache再生成で隠さない。
各記録の署名・scope・epoch floor・期限・最大経過時間を既存原本SDKで検査する。
基準descriptor原本、両catalogの正確な保持閉包を確認し、元DEBから両catalogを再観測する。
差集合は昇順の原本を線形比較する。過剰な行や、件数だけ合う別原本も拒否する。
依存・保護・phase・所有権の検査は既存native intent等の別条件であり、この集合検査では代替しない。

呼出直前に採取する独立UTC秒Nowと有限BOOTTIME deadlineを要求する。同期I/Oや処理の経過を
秒へ切り上げて加算し、準備したmapのCAS書込み後にも期限を確認する。Verifyのmap読取り時間も含む。
外側のプロセス期限とメモリ上限は引き続き必要。OS時計を変更するAPIはない。
Valid_Untilは各記録の期限と最大経過時間から求める最短の排他的UTC期限である。
0は失敗、又は成功した空の差集合を示すため、Statusを必ず併せて判定する。
空集合でもfinite deadlineと独立した有効なNowは必要で、署名検査の省略を任意の非空集合へ適用しない。
失敗したPrepareはAddressとValid_Untilを消すが、既に書かれた未参照mapが残る可能性はある。

Check_Retentionはmapとすべての直接参照、供給記録の全参照の存在/hash/形式を再生成なしで検査する。
これは時刻や鍵の認証を行うAPIではなく、期限が過ぎた過去世代を保持・参照するための構造検査である。
返却結果を新規導入の許可として用いない。保持検査だけでは基準の全履歴閉包を辿ったことにはならない。

## 認可との接続境界

Context.BeforeはこのSDKにとって呼出側の主張である。実root.stateから選ばれた基準であることを
公開主体が同じwriter予約下で証明する必要がある。妥当なdescriptor原本の存在だけでは不十分である。
NIAGEN04は保持policyを介してmapを認可対象の物理計画へ束縛する。
Publishは実root.stateと完全journalを監査し、新規admissionと記録済みtransactionの復旧を区別する。
詳細は[公開供給ポリシー](publication-supply.ja.md)。Recheck_Atは保持観測時刻で署名・原本を
検査する内部APIであり、それ自身が記録済み状態を証明するわけではない。新規admissionでは
Verify又はVerify_Intervalと独立した現在policy/時刻を使用しなければならない。
製品key/policy配備、rollbackに耐える時計/floor、失効後回復、全量性能、typed GCは未完である。

公開管理コマンドや第二の導入済みDBは追加しない。独立署名接続は開発用fixtureであり本番鍵ではない。
標準checkでは実TUF/OpenPGP発行結果をnative mapまで渡し、Pythonで正規preimageを独立に組み立てて照合する。
