# niayan採用コマンドの配布checkpoint

management 0.1.0の実DEB/対応sourceをDistroboxのdebhelper/dh-pythonで構築した。
source-inputs.jsonはexportした正本とmode/hash、artifacts.jsonは実成果物のSHA-256。
固定container 76d5c00dfa833ce7ae67a192c5663d9bcd5c4104153f5933431dae88c097918cに
導入し、12入口のhelp、非rootの媒体索引/一覧、日英の表示差、未接続変更の拒否、purgeを確認した。
CLIの応答互換性全体、全言語、導入済み台帳の更新を受入したことにはしない。

同じ固定containerで旧nia aliasを撤去したcontrolcoreを新規source treeからbuildした。
2 mainのリンク成功であり、全体試験・全証明・稼働daemon接続ではない。
controller implementation fingerprintは5f6c7925fcdcc4851c0c57dba00db34abde8a8845a29aa8a9112651ec2d5cc88。
C/FFIと共有契約は不変。各jobは3 GiB/swap0/CPU1/pids128のscope内で逐次実行した。

初回のローカル構築準備では実行wrapperの相対path誤りとdh-python不足を修正した。
依存導入後に実packageを構築している。これらを製品の成功試験として数えない。
niayan ISO、完全置換、本番認可・更新・起動・復旧は未完。

## GitHub配布CI

初回run 34716536899（workspace f1599f9）と、軽量builderを使うrun 34716711208
（workspace da62319）が成功した。後者のmanagementは0.1.1で、翻訳の原著作権・訳者表記を維持する。
各runの対象commit・URL・artifact hashはci-first.json/ci-current.json、実配置ログも同梱する。
GitHub上のsubmodule取得、2 source packageの実build、採用12入口と媒体/翻訳、識別情報の
install/reinstall/remove/purgeを検査した。全workspace compile/proofやISO起動のCIではない。
2つの既存CI成果物のうち不変の識別packageを比較した結果はidentity-rebuild.json。
managementは版と入力が異なるため、この比較の対象にしない。
