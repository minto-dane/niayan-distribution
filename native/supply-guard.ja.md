# 保持処理中の供給設定の継続観測

root-preparation 0.14.0 sourceの`SupplyGuard`を`Supervisor`の必須引数にした。
独立した計画器が選んだ世代、root/transaction、plan、retained policy、supply mapと、
計画時の供給設定/floorのSHA-256、観測UTC、元BOOTTIME期限を`Binding`へ渡す。
`Pkg_Site_Supply.Observe_Inputs`は同じnative sessionの設定を再認証してhash/UTCを返す。
入力を同意後に取り直して計画時の値の代わりにすることは禁止する。

`pkg_supply_guard`はroot保護された固定ELFをpinして、専用`nia-trust` identityで起動する。
パッケージwriter/signing identityとUID/GIDを共有せず、補助groupを空にし、bank/CAS/peer FDを
継承しない。native runtimeはdumpabilityを無効にする。設定は固定の`/etc/niaos/supply`と
`/var/lib/niaos/trust`から読み、rootの代わりに読むfallbackや権限変更は行わない。
標準の初回配備は公開入力を0444で保存する。制限した独自配備では専用identityの読取権限が必要。
これはファイルシステム全体をread-onlyにしたsandboxの保証ではない。

子は元期限を延長せず、1から1200までの順番付き8-byte要求へ72-byte応答を返す。
応答は`NIASUP01`、sequence、観測開始/終了BOOTTIME、完全bindingのSHA-256、観測UTC。
整数はbig-endian 64-bit。bindingの248-byte表現は`NIASUPB1`に続いてgeneration(32)、
root(16)、transaction(16)、plan/retained policy/map/policy hash/floor hash(各32)、
minimum UTC(8)、deadline(8)。ハッシュは文脈の取り違え防止で、署名や独立の認可ではない。

native readerは毎回、所有権/保護された祖先/型/リンク数、元設定とfloorの完全hash、
方針有効期間と失効下限、実UTCとsession内の時刻後退を検査する。変更された設定を
同じsessionへ取り込まない。CAS予約を取り直さないため、保持中workerとの予約競合を作らない。
親は元期限、child pidfd、最大1秒の応答時間、sequence、binding、UTC単調性、
余剰/未要求応答を検査する。失敗した子の再起動やobserverの再生成はしない。

Supervisorはoperatorと供給観測を同じ有限event loopで扱う。継続中は250ms間隔で要求し、
各root効果境界では、その境界より前に開始された要求とは別の両観測を要求する。
効果の直前にも各観測の鮮度とnative Admissionを検査する。子停止/期限切れ/拒否時は
controller切断を先に行い、その後observerを回収する。完了不確定な効果を成功や未実行と
扱わず、attempt/復旧記録を消さない。OS停止時間や瞬時の原子的な失効通知は保証しない。

供給観測はroot-owned方針の現在性の確認であり、retained map/receiptの内容、現在の世代予約、
計画の実行権限を証明しない。`Admission.check`にも同一Bindingを必須で渡し、計画器の保持文脈と
照合させる。native publisherの必須供給callbackや他のmanaged guardを削除してはならない。
実計画器・世代認可provider・公開launcherの接続、独立floor anchorは引き続き未完。

利用者指示に従い、この変更のコンパイル・型検査・挙動/障害試験・形式保証は未実施。
新規試験コードを追加せず、リリース前の統合検証で、計画後の方針変更と子停止/遅延時の
実効果遮断、通常更新、異なるbindingの拒否を既存の実root経路で受け入れる。
