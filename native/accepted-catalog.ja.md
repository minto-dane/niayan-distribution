# 確定済みカタログの照会と更新計画

`Pkg_Generation_Reader`へ確定状態の読み取りを独立させた。Publisherの既存read APIも同じ
実装を呼ぶ。共有する状態/plan/manifestの読み取りは`Pkg_Generation_Storage`に置き、
照会のために書き込み用の認可callbackを作らない。旧実装の検査を省略していない。

readerは既存publication/root/CAS予約を取得し、root.id、root.state、accepted plan、
descriptor、manifest pin、terminal journalの一致を検査する。catalog/transitionでは
保持closureを先に検査してから原本を読み、最後に確定状態と期限を再照合する。
予約中の変更、初期状態、欠損、進行中のtransactionを空の導入済み一覧に置き換えない。
原本からの解析で同じ内容の派生CAS objectを保存する可能性はあるが、確定状態は変更しない。

`Pkg_Update_Planner.Prepare`は実predecessorの同じ三予約の下で、native DEB transitionと
保持intent、実供給observer、target-minus-predecessorのmap/保持policyを作る。
独立に指定したExpected_Currentが現行descriptor hashと異なる場合は拒否する。
結果には実predecessor/closure、target/closure、intent/transition binding、map/policy、
供給設定/floor hashと観測UTC/有効期限が含まれる。成功時Siteは元のplanning sessionを保つ。
全失敗で結果を消去してSiteを閉じる。既に作ったCAS objectやTUF checkpointを消さず、再試行しない。
後続は実physical planを作ってBind_Publicationし、実行時に現在の世代と全managed gateを再検査する。
この処理はtargetの自動選択、全DEB効果のcompile、root組立て、実行認可、世代公開やboot切替ではない。

採用コマンドの`lslpp -l`と`lslpp -L`は、新しい`niaos-package.socket/service`を経由して
`pkg_catalog_query`をnia-pkgとして起動する。root/state/store/root IDはroot保護された
`/etc/niaos/package-query.json`から選び、要求のoperandをnative pathにしない。
問い合わせ元はkernel credentialsで照合し、元peer/pidfdと120秒以内の子の寿命を監督する。
未設定・未初期化・不整合・予約競合・子失敗は照会失敗として扱う。途中出力は公開しない。

配備JSONはversion=1、root/state/storeの三絶対pathとroot_idの32桁小文字hexだけを含める。
キーは昇順、空白なし、末尾LFのcanonical JSONとし、root所有かつ他者書込不可、保護された祖先の
通常fileでなければならない。root IDはinstallerが実際に確定したpublication rootの識別値を使う。
この設定を作るだけで導入状態を認証したことにはならず、native readerが実rootと記録を検査する。
架空の初期catalog、開発fixture、host dpkg DBへのfallbackは同梱しない。

一覧はnative name/version/architectureを維持し、確定したカタログの項目をCOMMITTEDと表示する。
これは選択済みカタログでの確定状態であり、現在bootしている物理rootの証明ではない。
名前とname:architectureへのglobを最大64個、各256文字まで受け付ける。`-q`は見出し省略、
`-c`は固定のFileset:Level:State:Architecture列とし、値中のbackslash/colonをescapeする。
-l/-Lの基本一覧を接続した段階であり、完全な出力互換性、説明/履歴/ファイル/修正照会は未完。

応答がsocketの一packetに収まらなくても一覧を切り捨てない。全native応答と成功終了/EOFを
確認した後、root所有のsealed memfdへ最大64MiBの完全表示を保存する。`NIAQRSL1`の96byte
応答はrequest ID(16)、descriptor SHA-256(32)、表示SHA-256(32)、size(8)を含み、FDは一つだけ。
clientはread-only要求の場合だけ受け入れ、root所有/リンクなし/完全seal/size/hashとUTF-8/制御文字を
検査して表示する。計画同意は引き続き既存の別形式と1MiB上限を用い、照会結果を同意や確定receiptにしない。

serviceは一度に一つのnative queryだけを実行する。最初の要求は2秒、同一UIDは10秒間に4件、
履歴は最大1024 UID、待ち行列は32、service全体は3GiB/CPU1/swap0/pids16に制限する。
未接続の変更要求は明示的に拒否し、旧workerや別PMへ委譲しない。重い原本再検査の高速化と
実機での公平性/操作性は出荷前に確認する必要がある。

root-preparation 0.15.0 / management 0.3.0 sourceへ配布構成を追加した。
インストール時のservice/socketの自動有効化・起動は行わず、開発環境の稼働状態も変更していない。
7言語のPO原稿と抽出対象を更新したが、POT/MO再生成を含むbuildはリリース前へ延期した。
既存MOは今回の新しい文字列を含まず、その部分は英語fallbackになる。全言語完成とは数えない。
コンパイル/型検査/挙動・障害試験/形式保証は未実施。既存fixture/本番CIの新APIへの追随も出荷前に行う。
