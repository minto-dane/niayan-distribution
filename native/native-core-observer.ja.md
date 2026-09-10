# native coreからの独立供給認証

`Pkg_Archive_Observer.Observe`は、既存の非root native coreと配布済みarchive observerを結ぶ内部SDKである。
公開管理コマンドは増やさない。判断ADR-0093、要求REQ-131。

## 呼出契約

呼出側は開いた`MC_Store.Store`を保持し、元DEB・control・InRelease・圧縮Packages・keyringの
五原本をあらかじめCASへ保存する。独立site設定から得たscope/key/epoch/ageとobserver UID、
相関ID、索引/DEBの相対UTF-8 path、最長130秒の排他的BOOTTIME期限を渡す。
応答や保持policyから独立authorityを生成しない。UID解決とsite配備の責任は呼出側にある。

SDKは原本をCASで再hashし、三原本の借用read FDを固定SEQPACKET socketへ送る。
Storeの予約FDは送信・再取得・解放しない。root所有systemd listenerと専用UIDの実SCM_CREDENTIALSを区別する。
正規JSONの相関/hash、二つのread-only sealed FD、容量、有限期限を検査する。
通信は一回で、自動retryは行わない。

native側で署名domain、独立公開鍵、scope、五原本とpolicy hashを検査した後、同じStoreへ
policyとreceiptを保存する。元DEBからのcontrol再観測、全保持原本、署名の期限/age、現在UTCと
経過BOOTTIMEを既存`Verify_Original`で確認する。拒否時はreceipt/policyの両出力を消す。
通信送信後の不確定な失敗を未実行と断定しない。サービスの明示拒否にもTUF checkpoint進行の可能性がある。
未参照CAS objectの回収は別の有界GC工程であり、失敗時に勝手に消さない。

## 供給計画への接続

返されたreceiptを`Pkg_Supply_Map.Sources`へ入れ、現在catalog/closureと独立authoritiesを使い
`Prepare`/`Verify`、`Pkg_Supply_Policy.Prepare`/`Verify_New`/`Check_Retention`を同じStoreで呼ぶ。
新規原本を必要とする計画がreceiptを省略すれば拒否する。
これは供給認証であり、同意・DEB効果・全managed guard・世代公開の許可を付与しない。
現在site trustの再観測と全admissionへの接続はproduction controllerの責任として残る。

## 検証範囲

標準Ada mainは閉鎖Store/期限/UID/保持原本欠損と二出力消去、競合writer排除を検査する。
CのUTF-8/path/JSON処理はASan/UBSan付き境界検査を持つ。
VM helperの`--native`は実native driverから実配布observerを呼び、実HTTPS取得中に別FDで
同じCAS lockの競合を観測する。accepted caseはcatalog/closureと供給map/保持policyまで検証する。
別control/UID、service設定/状態/鍵/TLS拒否を扱う。root caseはnative APIが通信前に拒否する。
`--native`なしの既存Python client検証も保持する。

VMのCA/TUF/key/原本とroot contextは人工fixtureで、本番siteの認定・installer・公開controller・
全DEB効果・実boot切替の受入ではない。過去DEBのhashはサービス配布物だけを指し、
新SDKが既存六appへ呼出接続されたという意味ではない。
