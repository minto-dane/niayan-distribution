# 独立した現在trustを使う供給計画

`Pkg_Supply_Planner.Prepare`は既存の開いたCASと計画用site sessionを受け、元DEBの供給認証から
供給map/保持policyまでを同じwriter予約で作成する。内部controller向け処理である。判断ADR-0094。

## 計画と公開の状態

計画前にはphysical plan/retained policy/mapはまだ存在しない。`Pkg_Site_Supply.Open_Planning`は
root/transaction、独立policy/floorの保護directoryと有限期限だけを受ける。
初回読取で完全なpolicy/floor hashと現在UTCを固定する。`Observe_Planning`は同じ入力を再読取し、
公開用mapを持たないsnapshotを返す。計画中のsessionを公開用`Observe`へ渡すと拒否して閉じる。

供給計画とphysical planができたら`Bind_Publication`へ実際のplan/retained policy/mapを渡す。
全hashは非zero必須。既存のpolicy/floor pin、UTC高水位と期限を引き継ぎ、前後で再観測する。
公開用sessionへ一方向に遷移し、計画状態へ戻す要求やcontext不一致は拒否して閉じる。
この束縛は呼出側contextであり、実rootや世代実行の認可ではない。

## 供給計画の処理

呼出側は保持済みcatalog/closureと正確なpredecessor、原本昇順の要求を渡す。
各要求にはscope・相関ID・五原本hash・索引/DEB pathがあり、公開鍵や時刻は渡さない。
observer UIDは独立した配備accountから呼出側が解決する。

処理は現在の保護site設定からscopeのauthorityを選び、各要求前に同じtrustを再確認する。
実`Pkg_Archive_Observer`へCAS原本を渡し、同じStoreへ返却receiptを保存する。
一要求の通信期限は全体期限と125秒後の早い方で、retryや期限延長を行わない。
既存`Pkg_Supply_Map`が両catalogを再検査し、target-minus-predecessorとの完全な一致を要求する。
そのmapを保持policyへ保存し、現在siteの独立authority/UTCで`Verify_New`を行う。
最後にもtrust/期限を確認してから三出力を返す。新規原本のない計画のValid_Until=0は既存契約通りである。

失敗時はmap/retained policy/valid-untilをzeroにしてsite sessionを閉じる。CAS予約は呼出側が保持する。
認証済みの未参照objectや進んだTUF checkpointは残り得る。自動削除やinstalled-state変更を行わない。
信頼設定の変更・欠損を、新しい設定として途中で採用しない。

## 検証と限界

実observer VMの追加計画caseは、root保護のsite設定/floorを使い、実HTTPSと署名から保持計画までを通す。
実HTTPS GET中のpolicy/floor更新とfloor欠損では、入力変更に到達したことと出力消去、session停止を確認する。
計画から公開への状態制限と、公開用callbackが計画用sessionを拒否することも確認する。

plannerが受けるpredecessorはcaller assertionで、実admissionが現在root.stateとの一致を証明する必要がある。
全managed認可・停止barrier・効果契約・health・世代公開・公開コマンドはこの処理だけでは実装されない。
本番site鍵/floor/時刻/installer配備、全DEB効果、実boot/復旧、完全置換ISOと全翻訳は別の未完工程である。
