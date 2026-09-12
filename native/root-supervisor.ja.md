# root実行の統合

`root_supervisor.Supervisor`は内部のroot所有者が使う処理で、公開listenerや
認可済み要求を作るlauncherではない。独立に選択したScope、bank FD、device plan/boot、
実operator peerと必須Admission providerを渡す。providerは現在の供給・世代予約・
正確な計画同意を有限・非blockingで検査し、失敗時は例外にする。既定実装は用意しない。

`prepare(Channel)`は非root子のnative要求を受信し、現在認可を確認してから既存controllerへ
実archive/CAS FDを渡す。認証対話中はcontrollerへ接続しない。応答中も同じloopで
operator/子/peer/controller/元BOOTTIME期限を監視し、最後に独立root FDと元記録を照合する。
応答に記されたinodeを期待値へ転用しない。FDコピーの解放後だけnative ACKを送る。

`reinspect(Channel)`は別のchannelで元期限と独立identityを固定し、同じcontrollerの
Observeへ接続する。元sessionの寿命を延長しない。保持中の待機は`wait_readable`を使い、
ownerが別のblocking作業を行わない。背景threadが自動的に監視していると仮定しない。
各効果境界では新しいoperator観測を消費し、継続中は250ms間隔で再確認を要求する。
実OSの停止時間やpolkit外部条件まで保証する値ではない。

取消/失敗時はcontroller接続を最初に切り、既存worker monitorへ停止を伝える。
その後channelとobserverを解放する。`finish()`のEOFだけがcontroller自身の解放確認で、
abort/期限切れ/例外を完了済みrollbackとはしない。永続attemptや記録を削除しない。
外部特権writerの排除、電断後の復旧、catalog/boot公開は別の未完条件である。

Ada側の`Pkg_Generation_Execution`は、必須Stage認可/設定/独立root観測/lifetime providerと、
二つのnative handoffを組み合わせる。v5/v6 manifestを初期化し、最大512batchを順に処理し、
root準備後に再検査してgeneration/root/CAS予約を保持する。借用FDや永続形式は変えない。
`Start`は一度限り、変更開始後の失敗はIndeterminate、`Check`失敗後は成功観測を出さない。
`Close`は予約を解放し、修復や再初期化をしない。これ自体はcatalog/boot公開器ではない。

Adaの追加provider phaseは`execution:bind`、`execution:advance`、`execution:prepare-root`、
`execution:root-prepared`、`execution:reinspect-root`、`execution:root-reinspected`、
`execution:held`、`execution:held-observed`。既存Stage内部の必須phaseも引き続き実行される。
本番provider、採用コマンドからのlauncher、署名された正確な計画同意は未接続。
この接続がない状態でservicesを公開・自動起動してはならない。

現行sourceの全面レビュー/形式保証/負の試験/実機受入はリリース直前に行う。
途中のfixture実行結果は[evidence](../evidence/native-transition/root-supervisor-01/README.ja.md)に
対象sourceと失敗を含めて保持する。部分成功を全製品の安全性やACID保証に読み替えない。
