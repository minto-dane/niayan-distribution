# 配布可能な内部archive observer

`niaos-archive-observer`は、専用UID `nia-supply`で一要求ずつ起動する内部サービスである。
既存TUF cacheと標準HTTPS取得器、OpenPGP原本認証、credential署名providerを接続し、
native core用の供給receiptと認証policyを返す。導入済みpackage DB、世代writer、任意script実行器は持たない。
一般利用者向けの追加管理コマンドではない。公開installp等からのcontroller接続は別の工程である。

## 配備

`prepare_service_package.py --component archive-observer --output <新規directory>`は、
必要な11 Python moduleとDebian packagingだけを正確に輸出し、source-inputs.jsonにhash/modeを残す。
既存root-preparation輸出の既定動作は変えない。Debian 13のdebhelperでbuildする。
Python、python-tuf、cryptography、requests、gpgv、zstd等は上流Debian依存として利用し、改変しない。
内部entryとclientは`/usr/lib/niaos/archive-observer/`、起動entryは`/usr/libexec/niaos/archive-observer`。

package導入はsysusersの専用UID/groupと停止unitを配置する。socketやserviceを自動起動/enableせず、
既定root、署名seed、site設定やTUF cacheは作らない。`nia-pkg` groupを用意し、実core accountは
既存root準備/controller側の配備を使う。account未配備やUID0のpeerは要求を満たせない。

installerがroot所有・他者書込不可の祖先と通常fileで次を配備する。

| path | 内容 |
| --- | --- |
| `/etc/niaos/archive-observer.json` | 独立repository identity、observer公開鍵、許可scopeと下限 |
| `/etc/niaos/archive-root.json` | 独立hashへ一致するTUF初期root原本 |
| `/etc/niaos/archive-keyring.gpg` | TUF認証policyがhash/fingerprintを指定するOpenPGP keyring |
| `/etc/niaos/credentials/archive-seed` | root managerだけが読む0600の32-byte Ed25519 seed。親0700 |

設定のschemaは`org.niaos.archive-observer/v1`で、root_sha256、metadata_url、targets_url、public_key、scopesを必須とする。
scope rowはscope、target、codename、minimum_security_epoch、maximum_lifetime_secondsの厳密な集合。
最大64 row、scopeの昇順・一意性、repository identity/targetからの再計算一致を要求する。
HTTPS URL、Debian13 pocket、epoch 1..2^53−1、lifetime 1..3600秒を検査する。
秘密鍵やscopeを要求側から設定する入口、実運用で使える人工の既定pinはない。

明示的な`niaos-archive-observer-provision.service`だけが、systemd StateDirectoryで非公開の
`/var/lib/niaos/supply`を準備し、排他的bootstrap intent、正規Repository.initialize、完了記録を順に永続化する。
既存intent/cacheへの再実行は拒否する。失敗時の部分状態を自動削除して再開しない。
この明示操作でも鍵やpolicyの正当な配備、rollback耐性を自動的には証明しない。

通常の`niaos-archive-observer.service`はStateDirectoryを使わず、ReadWritePathsで既存stateだけを開く。
非公開directoryの所有者/mode、bootstrap intentと完了の一致、初期root identity、既存lockを要求する。
通常起動時のdirectory作成・所有者変更・cache初期化を行わない。現在の設定は要求の前後で再読する。
bootstrap記録のconfiguration hashは初期配備の履歴であり、正規の後続設定更新との一致までは要求しない。
同じroot identityとbootstrap履歴を保持した設定/key更新は、installerが独立site policy/floorと調整する必要がある。

## 内部通信

`/run/niaos/archive-observer.sock`はsystemd所有のAF_UNIX/SOCK_SEQPACKET socket、0660 root:nia-pkg。
coreの実UIDをSO_PEERCREDで照合し、1 packet/4096 bytesとSCM_RIGHTSの正確な3 FDを受ける。
要求はcanonical JSONでschema `org.niaos.archive-observer-request/v1`、request_id、scope、index、debを持つ。
request_id/scopeは非zeroの64文字lowercase hex。index/debは1024文字・32要素以内の安全な相対path。
request_idは相関IDであり、署名済みtransaction IDや重複排除記録ではない。

三FDは順にInRelease、compressed Packages index、元DEBの読み取り専用通常file。
サービスは各上限16/256/512 MiBを守り、offsetを動かさずpreadで私有snapshotへコピーする。
元FDの属性変更、既存copy先、期限を拒否し、以後の認証は私有bytesに対して行う。
snapshotのpocketは保護設定から決め、認証policyと原本の意味検証は既存intakeへ任せる。
TUF/HTTPSは製品の標準Repository経路を使い、要求によるfetcherやTLS検証の差し替えは認めない。

成功応答はschema `org.niaos.archive-observer-result/v1`、request_id、status=authenticated、
receipt_sha256、policy_sha256、execution_permit=falseと、receipt/policyの二つのFD。
FDはread-only、0400、WRITE/GROW/SHRINK/SEALをすべてsealしたmemfdで、packetサイズへ大きなpolicyを詰め込まない。
clientはsystemdのlisten主体に加え、kernelのSCM_CREDENTIALSで実応答者nia-supplyを確認する。
相関ID、FD所有/mode/seal、hash、署名、scopeと現在時刻を確認する。
受信したすべてのFDを成功・失敗とも閉じ、呼出元の原本FDは借用のまま保つ。

拒否はstatus=rejected、execution_permit=falseを返す。例外本文や秘密情報を診断へ入れず、
固定phaseと例外classだけを記録する。TUF checkpointがすでに進んだ可能性はあり、拒否を無変更の証明にはしない。
native coreは別途、実CAS原本/control、site epoch/age、公開計画の全供給網羅性と実reservationへ結ぶ必要がある。
供給receiptだけで同意・DEB効果・世代公開・bootを許可しない。

## 制限と検証

process全体125秒、処理内120秒、socket入出力timeout、1 GiB RAM/swap0/CPU1相当/32 tasksを設定する。
起動回数は120回/60秒、backlog8に制限する。private tmp/device、ProtectSystem=strict、
capabilityなし、NoNewPrivileges、core dump禁止等を使う。巨大な許容入力が資源上限へ達した場合は
失敗し得るため、すべての最大値の同時処理能力を認定したものではない。

単体試験は設定/packet/FD/コピー/期限と終了時closeを扱う。VM受入工具は実DEBを導入し、
package導入時の停止、明示bootstrapと再実行拒否、標準HTTPSと一時CA、実systemd credential、
実native CASまで接続する。連続要求、peer、原本改変、設定/state保護、別鍵、不信頼TLS、lock欠損を確認する。
一時root/CA/署名鍵と人工DEBはVM fixtureであり、本番policyや完全置換OSの認定ではない。

この配布物をinstallerの配備計画へ組み込むこと、site key更新/失効とfloor/時刻の運用、
全共通供給のcontroller接続、全managed認可、全DEB効果、起動切替/復旧、完全置換ISOは引き続き必要である。
