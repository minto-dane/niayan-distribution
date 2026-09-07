# 現行ベース: openSUSE Leap 16.0 のみ

現行の有効profileは`profiles/leap-16.0.json`だけ。SLES契約・登録・SCCを要求しない。
SUSE Linux Enterprise由来のソースを使うことと、SLESの有料リポジトリを使うことは別。
openSUSEの公式説明はLeapをSLE由来とcommunity開発の組み合わせとしている。
一次資料: https://get.opensuse.org/leap/16.0/

旧SLES profileは`docs/historical-profiles/`に履歴として保存したが、現行distroctlは
読み込み・再投入を拒否する。Leap名で偽装した別供給元も受け入れない。
現在のURL許可はHTTPSのdownload.opensuse.org / downloadcontent.opensuse.orgのみ。
これは正確なRPM署名・鍵の信頼を代替しない。署名済みlocal snapshotを作る上流の
取得・redirect・ミラーの検証も別責任。契約不要とすべての再配布権を同一視しない。

通常のmutable更新を使用する。kernel/security policyの詳細は固定profileを参照。
元のネイティブZypper/RPMDB管理者は安全な所有権移行が完了するまで残す。
新しいresolvercoreは候補判断を独立に検査するもので、native RPMDBを二重管理しない。

libsolvを第一提案器、CaDiCaLを別のBoolean提案器として用意する。どちらの出力も
実行許可でない。新しいrelease gateはnative closure、independent model/order検査、
coverage/freshnessとruntime接続を要求する。UNSAT証明は必須の通常更新工程ではなく、
「解なし」と断定する時だけ正確な閉集合と投影に対して要求する。

Leap 16.0の公式support期間24か月も更新計画に含める。長期に固定すれば自動的に
SLESと同じ保守契約やAIX/z/OS相当の認定が付くものではない。
