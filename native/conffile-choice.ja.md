# 設定候補・選択・保持一覧

`Pkg_Conffile_Choice`は元DEBと実local snapshotから内容選択の候補を作る内部SDKである。
判断ADR-0097。既存のStore予約を保持したまま、次の順序で使う。

1. Prepareへroot FD、root ID、transaction、上位intentのcontext hash、原本とpathを渡す。
2. AddressとPendingから対象候補と確認の要否を得る。
3. ResolveへそのAddress、選択値と必要な退避先を渡す。
4. 得られた選択/保持一覧のhashを上位管理計画へ含め、公開前にRecheckする。

原本は既存のnative DEB読取から再観測する。Prior_Originalは前回保持したvendor baselineの
原本で、未追跡ならzero。現在のpackage版と異なることがある。指定する旧原本は対象の通常conffileを
宣言していなければならない。incomingのremove-on-upgradeは元宣言から導出する。
通常削除/purgeは旧原本を要求し、新原本は受けない。宣言がなく同名の通常payloadがある場合やlinkは、
別の効果解釈を必要とするため拒否する。これらを完成済みのDEB効果に数えない。

## 候補を変えない

候補には原本・宣言・内容・local metadata、context/transaction、初期BOOTTIME期限を束縛する。
後の期限指定で初期期限を延ばさない。選択前に同じlocal snapshotを再確認する。
別候補、未解決の必須選択、選択の再束縛を拒否する。確認不要な場合に選択値を暗黙無視せず、
Unresolvedだけを受けて既定の計算結果を使う。未解決の必須選択とは区別する。

退避先はcallerが明示する。同じpathや祖先/子孫との重なりを拒否し、実rootで欠落を観測する。
不要な退避名や必要なのに空の退避名を拒否する。既存fileを置換せず、後から作られた場合もRecheckで
候補を無効化する。他package/他設定候補との全namespace衝突は上位の全root計画で確認する必要がある。
観測上限はPrepareのfile上限を退避先にも適用する。

旧local/new vendorの退避義務、結果内容、次回vendor内容とその原本を選択recordに保存する。
keep-localでも次回vendor原本は新しいものになる。通常削除/宣言付き削除では旧baselineを保持し、
purgeや新原本から省略かつlocal欠落の場合には現行baselineを解除する。
これは内容の決定であり、mode/ownerなど全属性の適用方針まで自動決定したという意味ではない。

## CAS record

多byte整数はbig endian。列挙値は型の宣言順を0始まりで記録する。raw pathは表示言語で変換しない。

|record|構造|
|---|---|
|NIACPR01|tag 8、root ID 16、transaction 16、context 32、旧/新原本各32、旧/新宣言各32、local metadata 32、旧/local/新内容各32、操作/現在種/旧追跡/新種各1、初期期限8、path長4、path|
|NIACCH01|tag 8、候補32、選択/結果/退避種/次vendor種各1、結果/退避/次vendor内容各32、次vendor原本32、退避先metadata32、退避path長4、path|
|NIACCF01|tag 8、候補32、選択32、個数4、昇順重複なしの参照hash各32|

参照集合は最大32個で、候補・選択、両原本/宣言、使ったvendor内容/xattr/ACL、
local内容とmetadata、必要な退避先metadataを含む。zeroの不在参照をobjectとして加えない。
metadata内の可視xattrはinlineで、元DEBが未列挙のtar属性や元archive bytesも保持する。
package全体の展開cacheやcatalogの保持集合とは別で、未使用cacheはこの集合に含めない。
集合record自身は上位保持対象であり、自分の参照リストへ再帰的には加えない。

Recheckは保持参照を再hashし、候補作成時の集合と選択に一致するrecordだけを扱う。
欠損原本を再生成せず、元fileと退避先の観測も再確認する。失敗時はsessionを閉じる。
Resolve失敗の二出力はzeroで、CASに残る未参照objectを成功の証拠にしない。

## 本番への残る接続

このSDKは署名付き利用者同意を検証するUI入口ではなく、callerの選択値を候補へ束縛する。
root/intentの真正性、原本の供給認証、package所有権、boot/phase/replay制御は全managed admissionが必要。
同じStoreは存続中ずっとopenでなければならず、close/reopenやFD再利用は許可しない。
特権属性observer、全属性選択・全namespace計画、世代保持とpin/GC、recordの独立したdurable reader、
再起動後の復旧、実root/boot公開は未完である。live sessionの再確認をcrash recoveryの代替にしない。
snapshotは楽観的観測で、privileged writerを凍結せず隠れた属性の完全性を認定しない。
