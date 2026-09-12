# 実polkitへの管理操作認証

source subject: `59811cc91ab37ecdd8140045803ffefd55e4ffe93d7cb9431fca64ce433e354a`。ADR-0116、REQ-154、HAZ-140、FAULT-153。

root supervisor用Pkg_Operator_Authorizationを追加した。accepted seqpacketの実peer pidfdとUID、独立に渡すplan/requestを
固定system busのpolkitへ照合する。元boottime期限は最大120秒。Checkは同じcontext、peer/取消/期限、unique ownerと
Changed通知を確認し、失効後の再利用を拒否する。借用FDを変更せず、limited controlled型で自身の資源を解放する。
このdecisionは供給、正確な計画への同意、native世代admissionや開始済み効果の遮断を成立させない。

固定containerでC/Adaと既存6アプリをcompileした。選択Ada mainの独立directory buildは同一bytesで、
SHA-256はe62bfc563ed55e4b11813aed0332f4ff043a7f5a71465a21546874bb8accf404。
418個のC/Ada/GPRビルド入力集合を正本へ照合した。全418unitのcompile件数ではない。
export後の非compile変更は生成CIへのmain登録とRPMのsystemd-devel依存宣言。RPM buildは未実施。
数学的入力は変更せず、全suite/証明は反復していない。構造/参照/lint/license/生成CIは成功した。

private bus/authorityの12項目が成功し、不正形式、challenge、retained ID、過大details、Changed、無応答、
fork/非root、期限上限とFD解放を確認した。同じ12項目のASan/UBSanも成功した。Python全体leak報告は無効で、
address/UB errorは停止し、FDは独立に実数検査した。初回fixtureのindentation warningによるcompile失敗と修正前sourceも保持する。
依存downloadの初回sgml-base版指定不一致と修正後logも保持する。

使い捨てDebian VMの実polkit 126-2で14項目が成功した。製品policyのdefault拒否、実UNIX_FD/UID subject、
限定root fixture ruleの成功、別plan/request/利用者の拒否、busy/変更context、実rule再読込、polkit再起動、
取消packet、peer終了、元期限、実Ada/C往復と環境変数で接続busを変えられないことを確認した。
fixture ruleはbuilderと固定plan/requestだけを許可し、試験後に削除した。実agent/PAM dialogは試していない。
C libraryはd87a19da393a7d5eb1add90a606e6dd3fd2a501058ac940bf7b47266c4b7588d。

内部service package 0.7.0へauth_admin（keepなし）のpolkit policyとpolkitd依存を追加した。
main DEB/dbgsym/dsc/source tar.xzの二重VM buildが完全一致した。main DEBは
56191f395fe77ac532dc6b7b4b7b78a31d0bc47436487fc01204d537e46d4346。
32 export入力、runtime archiveの10 file、DEB内14 module/unit/policyを正本へ照合した。
workerはb55000d2e21d96c8e75a9f36dda4bbcf5c77c9dbf42074fa39b1600b1c113322で不変。
controller/worker/unitのcode変更はなく、実root抽出を今回の新しい実行として数えない。
policyの英語/日本語以外の翻訳は未完である。

重工程は順次3 GiB/swap0/CPU1/pids128、VMは2 GiB/1CPU。今回の全jobは正常終了した。
終了済みVM overlayの67,117,056 bytes（64.01 MiB）を削除し、別の稼働VM、base、受入VM、source、package、SDK、logを保持した。

本番CLI→supervisor→非root世代SDKの認証済みhandoff、現在供給/世代admission、正確な同意、取消と資源遮断、
全writer排他、bank slot/GC、実root/boot切替・復旧、全DEB効果、完全置換ISO、全言語翻訳は未完である。
このSDKの受入を唯一のpackage管理主体や本番デプロイ完了に読み替えない。GitHub公開/remote CIは今回実行していない。
