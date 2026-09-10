# 内部root準備サービスの配布・実unit受入

対象subjectは`a07ca45f3cc978710477f81e60e59403c1062e7fbdc6c4a5cb3b1facb2c5ee9a`。
仕様は[service-deployment.ja.md](../../../native/service-deployment.ja.md)、判断はADR-0087。
専用account、root設定、保護mount、socket/serviceとELF workerをDebianソースパッケージとして配備した。

Debian 13 builderの二つの新規directoryで主DEBとdbgsym DEBが実バイト列一致した。
主DEBのSHA-256は`6013c429320602e42c657dcee90345bd21af81636af38f07b83e13f92c7ec75c`、
dbgsymは`06edbca453b1f09bbfeefc143bf6b54f6d2948e5dde9177a93aa9388bb0a46c1`。
最終レビューでArchitecture宣言をanyから受入済みamd64へ限定した。
変更はdebian/controlのこの一行だけであり、vm-repackage-01で最終レシピから両DEBを再現し、
vm-service-03で受入済みの両DEBと実バイト列が同一であることも確認した。
実行時のbuild依存版は各VMの`.buildinfo`へ保存した。同じbuilder内での比較であり、異なる全環境や
依存更新後までの再現性を認定しない。最終package出力の18入力は現行repoと完全一致した。inputs/source-final.jsonが最終入力で、
inputs/source.jsonは実unit受入時の一行変更前の入力である。

vm-service-03でDEBを導入し、sysusersが割り当てたUID 987の専用accountから既存Ada driverを実行した。
元人工DEBからNIAGEN05の世代と13 entryを作り、実systemd socket/serviceからELF workerへ渡した。
207 assertionが成功し、worker hashは`65b1d101670af68843c66e4fb44db78eccb4cf5b88214f8df951b87313377e22`。
以前のlauncher hashではなく、今回インストールしたELF自身のhashである。
fixture由来の認可・供給鍵は本番providerではない。Ada driverと固定SDKのlibraryは変更せず再使用し、
その全runtime入力hashをreport.jsonに保存した。新たなAda compile/proofや全suiteの再受入とは報告しない。

実unitの/devが四つの必要なcharacter deviceだけであること、/tmpと/var/tmpが空で読取専用であること、
bankのnodev/nosuid/noexec、MemoryMax/swap/TasksMax、二重初期化拒否を確認した。
パッケージ導入時にはbank/CASが存在せず、serviceもsocketも自動起動・有効化されなかった。
native SDK自身がCASを初期化した後、明示bootstrapでbankを作成した。

再起動後の履歴読取はvm-service-03で成功したが、続く欠損試験の独立性を修正した。
電源を切った同じdiskをread-only backingとする新規差分vm-resume-04で、修正した後半だけを実行した。
主DEBの再構築・再導入・native展開は繰り返していない。bank lock、CAS lock、設定の各欠損で
activationを拒否し、欠けたfileを再作成しなかった。各ケースで元inodeを戻した後に履歴を再読し、
最終resultはpass。保存extractedは過去の結果で、physical_revalidation/published/effects_appliedはfalse。

初回の失敗も保持した。compat 13のsysusers helper不足を明示呼出しで修正した。
/dev tmpfsとkernel保護の組合せはAPI mountに優先され、実際には/devを隠さなかったため、
配布した専用directoryと必要deviceの読取専用bindへ変更した。
後半試験は前の欠損で停止したsocketを次のケースへ持ち越していたため、各ケースを停止・復元で分離した。
さらにsystemdのreset-failedはsocketのtrigger counterを消さないことを確認し、既定2秒のwindowを
経過させてから再開した。rate limitや起動前提の検査を無効にして成功させてはいない。
初回全入力の完全snapshotとは主張しない。最終前半と修正後半の試験器はinputs/へそれぞれ保存した。

外側3 GiB/swap0/CPU1/pids128、VM2 GiB/1 vCPUを維持し、全VM/jobは終了済み。
ホストのpackage導入・root変更・実機試験は行っていない。VM disk、秘密鍵、runtime library、DEB binaryは
Gitへ格納しない。主DEBは私有lab native-service-deployment-01/vm-resume-04/に保持する。

製品installer/controller、独立認可/供給provider、容量予約、物理再検証/回収、全DEB効果、
起動切替、完全置換ISOと全言語翻訳は未完。通常起動の成立をディストリビューション完成と混同しない。
