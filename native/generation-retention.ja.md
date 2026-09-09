# 世代へ束縛したnative catalog保持

`NIAGEN02`は、[catalog保持閉包](catalog-retention.ja.md)のSHA-256を世代マニフェストへ
含める。既存の世代transaction pin → manifest → closure → 全掲載objectという参照を使い、
別の導入済みDBや重複した保持pinを作らない。
[ADR-0074](../../assurance/docs/engineering/adr/ADR-0074.ja.md)を参照。

## 形式と呼出し

160 byte headerと64 byteの分割recordは維持する。tagは`NIAGEN02`、0起点offset128の
32 bytesは非zeroのCatalog_Closureとする。分割transactionのSHA-256入力にも新tagを使う。
`NIAGEN01`は従来どおり同領域をzero予約とし、従来のtransaction導出を保つ。
未知tag・不正長・不正fieldは拒否し、Decode失敗時は出力recordを初期値に戻す。

候補構築側で`Pkg_Catalog_Retention.Prepare`を呼び、得たhashを新版manifestへ入れて
Encodeする。`Pkg_Generation_Manifest.Check`は従来のファイルプラン構造検査である。
`Check_Retention`は新形式を必須とし、同じ開いたCAS上で正確な閉包を検査する。

StageのProvision、Advance、Verify_And_Hold（Inspectを含む）は、native形式なら構造検査に
保持検査を追加する。PublishとRead_Current_Catalogはnative形式を必須とする。
旧形式による隔離stageの構造試験と記録だけのRead_Currentは維持する。
旧形式の記録読取成功をnative保持の検査済みと扱わない。

Stageの四入口とPublishには、BOOTTIMEミリ秒の有限Deadlineを必ず渡す。
Counter'LastはInvalid_Input、既に過ぎた期限はStaleとする。
認可callbackの前後にも期限を検査し、期限後に返った許可で先へ進まない。
同期hashや外部library呼出しは即座に中断できないため、外側のtimeoutと資源制限も必要である。
途中まで書いたjournalやpinがあれば保持し、Staleを「何も実行していない」と読み替えない。

## 予約と欠落

全掲載objectの存在とhashを、catalog Loadによる派生内容の再構築より先に検査する。
欠落したcacheが原本から再生成できても、この受入経路は失敗する。
明示的な候補再構築と同じmanifestの再検査を経て復旧する。

現世代native観測はpublication/root/CASの予約を保持したまま検査する。
公開では既存のstage/publication予約を保持するが、CAS予約はファイル実行器への移行時に
いったん解放する。将来のGCはimmutable pinからこの参照をたどり、予約規則を守る必要がある。
この変更はGCもobject/pin削除も実装しない。所有者やrootによる予約外の変更への証明ではない。

## 検証と範囲

二つの合成世代について、closure自身と全掲載memberを単独で欠落させる。
Provision前、Advance前、Verify_And_Hold前、Publish前、現世代native観測で、
再生成しないこと、未組立てroot/stateまたは確定済みroot.stateが変わらないことを検査する。
native観測の失敗出力、期限、認可中の期限切れ、構造的に有効な旧形式の公開拒否も検査する。
独立readerは元DEBから一覧を再計算し、実root.stateから世代、manifest、pin、保持hashと
全memberへたどり、欠落試験の実行集合も照合する。

対象はcatalog由来の物質化済み参照である。全履歴世代・認証・効果・復旧起動の保持root、
保持期間と安全なGC、本番admission、全DEB効果と全属性の実行、実root/bootと完全置換ISOは
別途必要である。試験のtree/versionは合成内容であり、元DEB payloadを適用したrootではない。
