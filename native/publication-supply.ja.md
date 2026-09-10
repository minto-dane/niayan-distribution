# 世代公開に束縛する供給ポリシー

[NIAGEN05](root-generation.ja.md)も以下の供給admissionと記録済み復旧の条件を維持し、
rootアーカイブの参照と格納内容の一致を追加する。

NIAGEN04はnative intentに加え、署名付き原本差集合と独立した供給ポリシーの観測を保持する。
新規に開始する更新と、実際に記録された更新の復旧を区別する。署名記録の期限切れだけを理由に
認可済み更新を新規導入へ読み替えない。一方、古い記録がCASに残っているだけでは新規実行を許さない。

## 保持形式

NIASPOL1は次のCAS原本である。整数はbig endian。配列の呼出側添字や順序は保存形式へ影響しない。

| 0起点offset | bytes | 内容 |
| --- | --- | --- |
| 0 | 8 | NIASPOL1 |
| 8 | 32 | NIASMAP1 hash |
| 40 | 8 | 検査対象として保持するUTC観測秒 |
| 48 | 8 | authority件数、0〜256 |
| 56 | 件数×80 | scope hash32、Ed25519公開鍵32、epoch floor8、最大経過秒8 |

authorityはscopeの厳密な昇順。重複、zero scope/key、無効な整数、切断、余剰を拒否する。
UTC秒・epochは1〜2^53−1、最大経過秒は1〜3600。空のauthorityは空の原本差集合だけに使用できる。
記録自体は署名済み許可証ではなく、認証対象計画の入力である。保持された鍵を自分自身の根拠にしない。

NIAGEN04のheaderは224 bytes。NIAGEN03の192 bytesを維持し、offset192の32 bytesへ
NIASPOL1 hashを追加する。batchはoffset224から始まる。transaction導出はNIAGEN04をdomainとし、
旧形式のbytes・transaction導出は変えない。descriptor→manifest→policy→map→receipt/原本が
既存計画・pinの保持参照となる。第二の導入済みDB、sidecar、別pin identityは追加しない。
型を理解して全世代を辿るGCの実装は引き続き必要である。

## 新規admission

Publishは同じpublication/root/CAS予約でroot.stateの実基準、native intent、保持原本を検査する。
独立したObserve_Supplyは、対象root/transaction/plan/policyに対して現在許可されたscope/key/floor/ageと
独立UTC秒を返す。保持policyの自己申告をコピーしてはならない。応答行はscope順でなければならない。

独立ポリシーの全件・全フィールドを保存済みpolicyと照合し、保持観測から現在までの区間で
各署名記録が有効であることを、元DEB/controlと正確な差集合から再検査する。
将来又は署名記録の観測前の保持時刻、期限切れ、鍵/floor変更、原本欠損は拒否する。
StageからEngineへの予約受渡し後、Engine.Check_Inputsで実際に保持するroot/CAS予約の下で
実root.stateの全フィールド、descriptor/manifest、全保持入力とnative検査をやり直す。受渡し前の
検査結果だけで処理を開始しない。その後も、既存Managed guardの前後で独立ポリシーと
新規供給の期限を確認する。callbackの処理時間とAPIのI/O時間を含む有限BOOTTIME期限を要求する。
独立時刻の逆行も拒否する。返却前にもdeadlineを確認し、遅いI/Oを期限内の成功として返さない。
その時点で永続決定が残る場合はあるため、失敗を未実行と解釈せず正確な計画を観測・復旧する。
ホスト時計を変更しない。

Engine.Prepareが成功するまでは新規admissionとして扱う。既存EngineのPrepared→active root.stateの
永続化規則を使用する。Preparedだけ残りactive stateに入っていない場合、再試行には新しい鮮度検査が必要。
検査と永続化の間の異常終了を、すでに公開済み又は未実行と推定しない。

## 記録済み復旧

復旧はroot.stateが正確なactive transaction/planを指す場合、又は正確なtarget generation/accepted planを
指す場合に限定する。既存Pkg_Recovery_Auditでpin、計画、ジャーナル全記録、root stateとの整合性を
確認してから、保持された供給観測時刻で署名と原本・差集合を再検査する。
古い時刻へ実際の経過時間を加算して、新たな期限切れを作ることはしない。現在のI/O deadlineは維持する。

現在許可された独立scope/key/floor/ageは復旧でも必須で、保持policyと完全一致しなければならない。
期限だけの扱いを変え、失効した鍵や引き上げられたfloorを自動で迂回しない。全Managed guardと
健康記録の認証も通常どおり適用する。鍵移行・失効後の回復policyや独立rescueは製品側の別の設計条件である。
Recheck_Original/Recheck_At/Recheck_Recordedは内部の歴史的検査APIであり、それ自体が記録済み状態を
証明するわけではない。公開側の実root/journal検査を省略して新規認可に使ってはならない。

## 互換性と残る範囲

公開入口はNIAGEN04を必須とする。旧v1/v2/v3の新規公開・再実行は拒否し、移行前の復旧には
保存された旧実装を用いる。旧v1の構造読取とv2/v3のnative読取は維持する。
NIAGEN03以前のroot.stateやfile-WALのbytesを無理に変更しない。

現段階の実行は非特権SDKである。本番Observe_Supply/Managed adapter、鍵・policy配備、rollbackに
耐える時刻/floor、全DEB効果、実root/boot、全量性能、GC、完全置換ISOの受入を代替しない。
テストのtree/versionはcatalog bytesの合成効果であり、実DEB payloadから作ったrootfsではない。
