# root supervisorのnative session SDK

source subject: `d7d795ce6286962f21fbfd61df1c851cc3c98fb939c705b4d103d0e14569dbbc`。ADR-0115、REQ-153、HAZ-139、FAULT-152。

root管理プロセス専用のPkg_Root_SessionとC transportを実装した。既存の非root世代SDKのUID/API/永続形式は維持する。
限定型のhandleで接続を保持し、明示scope/pin/実FD、root peerと各応答のUID/PID、正規応答全体、元期限を照合する。
Open/Observe/Close、使用中handle、観測失効と接続寿命、Ada Finalizeによる非待機切断を扱う。
返却inodeは独立観測ではなく、認可や起動許可へ変換しない。

固定containerで選択Ada mainと必要C/Ada unitをcompileした。root peer試験29項目が成功し、scope/identity/期限変更、
非正規/過大/切断、余分FD/control切詰めと受信FD解放、UID/PID変更、非root/fork、観測変更、期限、
明示CloseとAda Finalizeを確認した。ASan/UBSan付きCは28項目成功。Python全体のleak報告は無効で、
address/UB errorは停止する設定。FD寿命は別に実数確認した。数学的証明や全component suiteの再実行ではない。

独立したdirectoryでも選択Ada実行物が完全一致した。hashは
b72206be3a5177b62255cd47750957db06a43de122895b6104708096483032aa。
413個のビルド入力集合を正本へ照合した。全413unitを実compileした件数ではない。export後の差は生成CIの新main登録だけで、
実行したC/Ada/GPRとprotocol fixtureは現在sourceと同じbytesである。構造/参照/lint/license/生成CIも成功した。

実GPT/ext4 VMでは受入済み0.6.0 DEBと実initializerを導入し、新C libraryからprepare/observe/Closeを呼んだ。
workerによる実展開/RO全再検査、独立に開いたroot FDのmount/device/inode/RO、新CAS OFD取得とBank保持、
CloseのEOF、元tree/記録の不変が成功した。service/packageは変更・再buildしていない。DEB内13module/unitを正本へ照合した。
C library hashは7fdea19c1aaf352fa8c9d1615c6f120fa86bfdc445a2a2ca435b662ab35f4aae。
worker hashはb55000d2e21d96c8e75a9f36dda4bbcf5c77c9dbf42074fa39b1600b1c113322で不変。
Adaの実FFI往復はcontainer peer、実controller往復は同じC境界のVM fixtureで検査した。実世代SDK接続の認定ではない。

初回compileの異なる整数型をothersへまとめた不備を修正した。最初の入力snapshotは未保存で、失敗logだけを診断として保持する。
初回protocol成功時のthread/fork warningはpeerを別processへ変更して解消した。ADR見出しと生成CIの初期不一致も保持した。

重工程は順次3 GiB/swap0/CPU1/pids128、VMは2 GiB/1CPUで実行した。今回の全jobは終了した。
終了済みoverlayと追加diskの計49,909,760 bytes（47.60 MiB）を削除し、稼働中の別VM、base、受入VM、source/package/SDK/logを保持した。

本番site認可/供給/利用者同意・取消、非root世代SDKへの認証済みhandoffと独立observer、外部特権writer排他、
bank slot/GC、実root/boot切替・復旧、全DEB効果、完全置換ISO、全言語翻訳は未完。
今回のRPC接続は人工scopeの受入であり、起動許可や本番デプロイ完了を意味しない。GitHub公開/remote CIは実行していない。
