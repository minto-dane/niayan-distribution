# 管理者認証とnative操作の境界

`Pkg_Operator_Authorization`はroot supervisorが実際の接続元に対してpolkitの管理権限を確認する内部SDKである。
認証先はDebianのpolkitで、Nia独自のpassword DB、setuid入口、公開代替コマンドは作らない。
署名済み計画、供給、設定、効果、利用者が確認した正確な計画、native予約は引き続き別の必須検査である。
このSDKだけでroot sessionや世代writerを呼ぶdaemonは配備していない。

## 接続元と認証先

呼出側は受信した要求と各messageのkernel credentialsを先に認証する。Openには実accepted AF_UNIX/SEQPACKET FDを
借用で渡す。UIDを要求本文から受け取らず、SO_PEERCREDの接続元UIDとSO_PEERPIDFDのtaskを使う。
PID/start-timeへのfallbackはない。callerはrootでなければならず、subject UIDもpolkitのsigned32範囲内に限定する。
requestを消費した後は同じsocketへ新しいdataを送らない。取消packet、切断、接続元task終了でdecisionを無効にする。

接続先はroot所有の`/run/dbus/system_bus_socket`に固定し、祖先directoryのowner/modeとsocket種別を検査する。
環境変数のDBUS_SYSTEM_BUS_ADDRESSを利用しない。system busの所有権policyで保護された
org.freedesktop.PolicyKit1のunique ownerを固定し、そこへCheckAuthorizationとPingを送る。
polkit自体は専用非root accountで稼働し得るため、そのUIDをrootと決め付けない。
未稼働/未知owner、FD非対応、bus失敗は拒否し、自動的な別busやPID subjectへ切り替えない。

subjectはunix-process、pidfdはD-BusのUNIX_FD型`h`、uidはint32型`i`で渡す。
操作はorg.niaos.package.manageに固定する。detailsはnia.plan（SHA-256 hex）とnia.request（16-byte ID hex）だけである。
callerは独立に検証した不変計画と一度限りの要求からこのcontextを作る。自由文字列やverified=trueを送らない。
polkitはdetailsのnativeな意味を検証しない。detailsが一致するだけでplanへの同意や供給検証を成立させない。

## 一つの操作に限定したdecision

元CLOCK_BOOTTIME期限は最大120秒。Openでのみ対話を明示指定できる。許可とchallenge=falseの正確な応答形式を要求し、
返却detailsに一時保存済みauthorization IDがあれば拒否する。独自grant fileや他操作への認証cacheは作らない。
使用中SessionへのOpenはConflictで、既存contextを置き換えない。Ada型はlimited controlledで、scope終了時に資源を閉じる。

Checkは同じplan/request、作成process、接続元task/socketと期限を確認する。polkitのChangedを事前購読し、
同じunique ownerへのPingと通知処理、前後のowner再照合を行う。状態変更やowner交代、過多の通知、通信エラーで
decisionを永続的に無効にし、Closeと明示的な新しい認証を要求する。暗黙更新や再対話は行わない。
借用socketは閉じず、自分のduplicate、pidfd、bus接続だけを解放する。

これは認可判断の有界な寿命であり、開始済み効果の撤回ではない。Changedを伴わない独自ruleの外部条件、
whole-system rollback、特権改変、厳密なkernel I/O/対話終了時刻を単独で保証しない。nativeの現在policy/取消・writer予約を
実効果の直前にも再検査し、取消後の資源遮断と実観測へ接続する必要がある。対話timeout後はbus接続を解放するが、
画面消失を独立確認したとはしない。owner/UID照合だけで侵害された基盤を防御できるとは主張しない。

## 製品policy

内部サービスpackage 0.7.0は`org.niaos.package.policy`を/usr/share/polkit-1/actionsへ導入する。
any=no、inactive/active=auth_adminで、auth_admin_keepを使わない。無条件許可ruleを製品へ同梱しない。
Niaの管理権限確認という説明と認証messageを英語/日本語で持つ。残りのDebian対象言語への翻訳と実agentでの表示は未完。
この認証messageはpackage一覧や変更内容の確認画面ではなく、実計画の同意UIを置き換えない。

本番CLI→supervisorの認証済みhandoff、供給/世代admission、同意の表示内容digestと応答、全寿命の取消/遮断は未接続。
既存非root SDKのUID拒否を解除したり、polkitのtrueを全managed callbackのOKへ変換してはならない。

## 検証

使い捨てVMで実polkit 126、実pidfd subject、製品policyのdefault拒否、実root管理の狭いfixture rule、
別plan/request/利用者の拒否、実ルール更新通知、polkit再起動、取消packet、peer終了、期限とAda/C往復を検査した。
fixture ruleはbuilderという利用者と固定plan/requestだけを許可し、終了時に削除した。これは本番ruleや認証dialogの試験ではない。
隔離containerのprivate bus/authorityでは不正応答、challenge、retained ID、過大details、通知、無応答とFD解放を検査する。
正確なsource/package/binaryと件数はsource-bound evidenceに記録する。数学的証明とは区別する。

根拠: [polkit Authority](https://polkit.pages.freedesktop.org/polkit/eggdbus-interface-org.freedesktop.PolicyKit1.Authority.html)、
[PolkitUnixProcess](https://polkit.pages.freedesktop.org/polkit/PolkitUnixProcess.html)、
[upstreamのpidfd wire処理](https://github.com/polkit-org/polkit/blob/126/src/polkit/polkitsubject.c)。
API説明のint32表記だけに依存せず、実装のUNIX_FD handleとUIDの組を実Debian版へ照合した。
