# 認証原本とnative CASを結ぶ供給記録

`archive_receipt.issue`は既存archive intakeのTUF/OpenPGP認証を実行し、正確な原本hashと
期限をnative用の署名付き記録へ変換する。呼出側が独立に設定する署名providerと公開鍵pinを必須とする。
任意の観測JSONや`AuthenticatedArchive`を署名するAPIは公開しない。製品鍵の生成・保管、
既定authority、新しい公開管理コマンドは追加しない。署名providerの実運用配備は未認定である。

## 形式と適用範囲

署名は既存`MC_Authentic`と同じEd25519、署名対象は
`u16be(domain length) || domain || body`で、domainは固定ASCII `NiaOS/archive-supply/v1`。
bodyは256 bytes、末尾に64-byte signatureを付けた全320 bytesをCASへ保存する。
整数は符号なし64-bit big endianで、意味上の上限は2^53−1。余剰・省略・未知版を認めない。

| byte位置（0始まり） | 内容 |
| --- | --- |
| 0–7 | `NIASUP01` |
| 8–39 | 独立に指定する供給scopeのSHA-256 |
| 40–71 | 認証したpolicy envelopeのSHA-256 |
| 72–103 | 元DEBのSHA-256 |
| 104–135 | raw controlのSHA-256 |
| 136–167 | InRelease原本のSHA-256 |
| 168–199 | Packages索引原本のSHA-256 |
| 200–231 | OpenPGP keyring原本のSHA-256 |
| 232–239 | security epoch |
| 240–247 | 認証完了のUTC秒 |
| 248–255 | 返却を認める期限のUTC秒 |
| 256–319 | Ed25519 signature |

scopeはcanonical JSONの`schema=org.niaos.archive-scope/v1`、`repository`、`target`をhashする。
repositoryには既存cache identityのschema/bootstrap SHA-256/metadata URL/targets URLが入り、
targetは正確なpolicy target pathである。native側の期待scopeと公開鍵は保護されたsite policyから
与える。記録自身のscopeや同梱公開鍵を信頼設定として採用してはならない。

発行時は認証結果の期限と、認証完了時刻に明示lifetimeを加えた時刻の早い方を使う。
lifetimeは1秒以上・最大3600秒。署名providerの応答は独立公開鍵で検証し、保持TUF metadataと
時刻を再検査してから返す。逆行・期限到達・全発行処理120秒以上では記録を返さない。
providerに渡した署名要求が失敗しても、副作用のない未要求だったとは扱わない。
秘密鍵を引数・環境変数へ載せる経路は作らない。実際のproviderにも期限・資源上限が必要である。

## nativeでの照合

`Pkg_Archive_Supply.Verify_Original`は、既存Store予約下で記録のCAS原本を読み、独立scope・鍵・
epoch floor・最大経過時間と照合する。期待元DEB/controlも別入力とし、記録との一致を要求する。
署名検証後、policy/元DEB/raw control/InRelease/Packages/keyringをすべて既存CASから開き直して
hashを再検証する。この確認を終える前に派生cacheを再生成しない。
その後、native DEB読取器で元DEBのcontrolを再観測し、期待値と比較する。実際のcontrolが異なる
記録は、署名が正しくても拒否する。観測の過程で他の派生オブジェクトが残る場合はある。

現在時刻`Now`は呼出直前に信頼する時計から取得する独立UTC秒で、記録の時刻を渡してはならない。
処理中のBOOTTIME経過を秒へ切上げ、返却直前にも有効期限と最大経過時間を照合する。
絶対BOOTTIME deadlineも有限でなければならない。署名記録の期限・deadlineは到達時点で拒否する。
失敗時はBindingを消し、完全成功時だけ記録のCAS addressを返す。UID0では処理を開始しない。

## 境界と残る接続

native側は署名したobserverを認証し、CAS原本を再観測する。TUF/OpenPGPの意味検証を
native側で再実装せず、発行側の既存上流検証を使う。署名者の実装・適用範囲・鍵の運用は
信頼境界であり、署名したという事実だけで任意の申告が正しくなるわけではない。
通常原本の信頼cacheは既存TUF checkpoint一つを維持し、導入済みDBや別writerを作らない。

このAPIは一つの原本を照合するSDKであり、全公開計画の供給網羅性・保持閉包・writer予約への
束縛はまだ必要である。変更しない既存packageへ新しいmirror掲載を一律要求する設計にはしない。
本番observer/key/policy配備、rollbackに耐えるtrust floorと時計、全履歴のtyped retentionも未完。
同意・全DEB phase/所有権/効果・health・実root/bootの認可は供給記録とは別である。
この記録を実行許可に変換する既定callbackや公開入口はない。

## 検証

`test_archive_receipt.py`は実TUF/OpenPGP認証と一時鍵を使い、認証不成立時の署名非呼出、
独立鍵/domain、署名形式、provider障害、署名中の期限/時計/cache変更を検査する。
`run_archive_supply_tests`は全wire bytesの変更、署名済み不正値、独立policy、必要object欠落、
ネイティブcontrol不一致を検査する。単独component試験は上流metadataを人工原本として扱う。
`check_archive_receipt_bridge.py`が実TUF/OpenPGP発行結果をnative driverへ渡して原本/control/hashを
独立に照合し、別鍵・scope・control・破損記録も検査する。標準`make check`にこの接続試験を含める。
