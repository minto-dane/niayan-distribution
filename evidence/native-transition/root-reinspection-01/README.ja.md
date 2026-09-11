# 固定した実rootの非更新再検査

source subject: `3c627db797f2bc7dd6366149800642d07e36b826d1b7ad34cecf4b0e6bc8a496`。ADR-0110、REQ-148、HAZ-134、FAULT-147。

内部workerとBankサービスに、保持archiveと展開済みrootを現在照合する経路を追加した。
read-only/nodev/nosuid/noexecの実mount、元intentと現在worker、実bank/CAS予約を必須とする。
全tarを二回hashし、内容・数値owner/mode・宣言時刻・ACL・宣言flags・link/deviceを照合する。
xattrの完全一致、全directoryの列挙、正規path、子mount拒否とinode link groupも確認する。
応答は実mount IDとdevice/inodeへ束縛する。元rootとintent/resultは変更しない。

`vm-package-05`で実DEB `0.3.0` を導入し、正常と8種類の不一致を確認した。
書込可能rootと異なるgenerationの拒否、Bank再起動と実UID1000の二FD RPCも通過した。
全treeの内容・時刻を含む属性と保存記録の前後一致、呼出し元leaseの維持を確認した。
従来の実展開とBankのpeer/予約/worker/service中断試験も成功した。
最終worker SHA-256は `b55000d2e21d96c8e75a9f36dda4bbcf5c77c9dbf42074fa39b1600b1c113322`。

別directoryで二回構築したmain DEB、dbgsym DEB、source .dsc/.tar.xzがそれぞれ完全一致した。
23個のexport入力と実source package、4個のVM工具入力、実DEB内service/workerを正本・実結果へ照合した。
同一builder内の再現性であり、独立した第三者再ビルドの認定ではない。buildinfoも保持する。
成果物と対応source packageは私有labのvm-package-05/packagesに保持し、Gitにはログとhashだけを含める。
service unit検査は通過し、導入時のsocketは無効・非稼働を維持した。

初回VMのKVM権限拒否、旧時刻の二重build差分、再起動で消えたguest /tmpを参照した診断失敗も保存する。
古い差分の直接原因は確定していない。未来だったchangelog時刻を修正し、新規exportと永続guest directoryを
使った最終runで一致を確認した。診断用exportの手動修正による古いmanifestも最終runへ流用していない。
VM 02の初期workerは最終Cのxattr双方向照合とstatx mask確認より前で、最終版の根拠はVM 05である。
VM 06はbuildinfo等の取得だけであり、追加試験には数えない。

構造・参照・lint・license・生成CI整合性を確認した。Ada/数学的入力は不変で、全suite/証明は反復していない。
CI recipeへworker compileと必要依存を追加したが、新しいnative test image構築とremote CIは未実行である。
3 GiB/swap0/CPU1/pids128、VM 2 GiB/1CPUで順次実行した。全job終了済み。
今回の使い捨てVM差分4個、88.53 MiBを削除した。base/受入VM/source/package/証跡は保持した。

read-only bind viewだけでは他viewからのwriterを停止できない。観測は継続的な起動許可ではなく、
全writer/mount排他とSDKへの権限伝達、本番provider、実root/boot切替と復旧は次の実装である。
旧workerで展開したrootは自動移行せず拒否する。全DEB効果、GC、完全置換ISO、全言語翻訳も未完。
ctime/birthtimeや未宣言flags、全MAC policyの認定を含めず、未宣言xattrは拒否する。
