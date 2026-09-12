# root supervisorのnative session接続

`Pkg_Root_Session`と`root_session.c`は、独立したroot管理プロセスが0.6.0のcontrollerを呼ぶ内部SDKである。
既存`Pkg_Generation_Stage`と`Pkg_Root_Preparation`の非root制約、認可callback、永続形式は変更しない。
公開コマンド、権限昇格入口、稼働世代のwriterは追加しない。本番site認可/供給/同意providerと
非root世代SDKからsupervisorへ渡す認証済みhandoffは、まだ接続していない。

## 要求と応答

Openは独立に選んだgeneration/root manifest/archive/worker、stage、device plan hash、boot ID、bankの
mount/device/inode、有限CLOCK_BOOTTIME期限と借用archive/CAS FDを受け取る。正規JSONとSCM_RIGHTSを一回送信する。
root UIDの接続先を確認し、応答ごとのSCM_CREDENTIALSにroot UIDと最初の応答processと同じPIDを要求する。
socket activationのlistener所有者と実serviceのPIDは同一と仮定しない。root管理面は引き続き信頼主体であり、
特権processによるcredential指定、FD移送、PID再利用を単独で封じる認証器ではない。

応答全体は正規byte列へ照合し、同じdeadline/stage/初回期限、mount/device、非公開状態を要求する。
root inodeだけは初回展開後に決まる観測値として返す。整数範囲、余分なfield、NUL/末尾、切断、過大messageを拒否する。
返信のFDは一切採用せず、受信してしまったFDも全て閉じる。借用したarchive/CAS FDへclose/LOCK_UNを送らない。

## 寿命

AdaのSessionはlimited controlled型でコピーできない。C側は作成process PIDを保存し、forkしたコピーからの
操作を拒否する。socketはCLOEXEC/nonblockingで、待機は元のboottime期限に従う。暗黙再接続/再送/期限延長はない。
使用中のOpenはConflictで既存handleを維持する。受信後のOpen失敗はIndeterminateで切断し、既発生の効果を取り消さない。

Observeは新しい借用archive/CAS FDを送り、初回と完全に同じ観測を要求する。失敗時は有効な観測を失うが、
明示Closeまで自分のsocketを維持する。controller自身の期限切れや切断による予約終了を止めるものではない。
Heldはローカルな有効性・期限・未処理の通信異常の検査であり、現在mountや認可の検証ではない。
期限切れ後はObservationもゼロ値を返す。callerは同じhandleを複数taskから並行使用しない。

Closeは同じstageの終了要求を送り、元期限内のEOFだけを後片付けの応答として受け取る。自分のsocketは結果にかかわらず閉じる。
OKでも展開/公開/起動成功、外部writerの終了、supervisor自身のFD解放を意味しない。期限切れや通信失敗ではremote cleanupは未確認。
Ada Finalizeは自分の接続を閉じるだけで、待機やremote成功の宣言をしない。forkコピーの破棄でもshutdownは使わない。

## 世代SDKへ渡す前の残る接続

返却inodeから独立期待値を捏造しない。supervisorは保持中の実root FDを独立に開き、mount/device/inode/ROと
元記録を照合し、site認可/取消・供給/同意と外部特権writer排他を全寿命にわたり維持する必要がある。
その認証済み観測と借用予約を非root側のmandatory Observe_Root providerへ接続する工程は未完である。
本APIの成功だけで既存generation handleやpublication/boot permitを作れない。

## 検証

`pkgcore/tests/run_root_session_tests.adb`は標準台帳に登録した。通常実行は空handle・無効入力・Closeを検査する。
隔離UID0の`check_root_session_transport.py`は実C共有libraryとAda mainを使い、正規request/FD、全応答照合、
誤scope/identity/期限、非正規/過大/切断、返信FDとcontrol切詰め、返信UID/PID変更、非root、forkコピー、
使用中handle、観測変更後の無効化と予約寿命、期限、Adaの明示Closeと自動Finalizeを検査する。
これらのpeerとscopeは人工で、物理bankやsite admissionを認定しない。

`distribution/native/worker/check_root_session_sdk.py`は使い捨てGPT/ext4 VMで、受入済み0.6.0 packageと新C adapterを
接続する。実展開、全再検査、独立root FD照合、新CAS OFDの取得、Bank保持、observeとClose/EOF、元tree/記録の不変を検査する。
新たなservice packageは作らず、変更していないworker/unitは元packageのbyte列へ照合する。

通信仕様の根拠は[Debian 13 unix(7)](https://manpages.debian.org/trixie/manpages/unix.7.en.html)と
[recvmsg(2)](https://manpages.debian.org/trixie/manpages-dev/recvmsg.2.en.html)。
EOFと受信FD処理の実挙動は上記試験で確認する。SPARK外のC/FFI境界であり、形式証明とは区別する。
