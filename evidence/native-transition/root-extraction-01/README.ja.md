# 非公開rootの実展開

対象subjectは`864a37fa0fae58b6254ad8aa52167f221b0bf8023b34a1c0568eee98edb41e2d`。
最終workerは`427fbd5f115d97ad21fd03ddce1c7fd7d39d69b240c606248b8bddc4fa3394c8`。
[内部worker](../../../native/root-extraction.ja.md)を固定SDKで実compileし、使い捨てVMで確認した。

最終実行はbuild-stream.log、vm-check-stream.log、vm-stream/。10 entryの全7種類、
数値UID/GID・mode、ACL、宣言xattr、mtime/atime、内容、hardlink、device番号、root時刻、
日本語と非UTF-8の名前を読み戻した。別のPython読取でも実filesystemを確認した。
正常場合とhash/件数/期限/使用済みtarget/書込可能FDの五つの拒否が成功した。
最終binaryの非特権拒否も成功。供給やsite効果の本番認可、抽出rootのbootは行っていない。

外側は3 GiB/swap0/CPU1/pids128。VMは2 GiB・1 vCPU、既存builderをread-onlyで参照する
新規qcow2差分disk、guest通信制限とcontainer内loopback SSHのみ。最終QEMUとguest試験の
終了codeは0。基準builder全量の再hashやISO全体の再認定ではない。
固定SDK由来のloaderと全共有ライブラリを持ち込み、hashをreport.jsonへ保存した。
SSH工具のhost入力hashはssh-tools.json。秘密鍵とVM diskはGitへ含めない。

診断実行は最終結果と分離して保持した。初回の不足capabilityと、追加後もDistroboxの
外側でmknodが拒否されることを最小操作で確認した。制限を全面解除せずVMで全種類を確認した。
最初のVM工具imageにSSHがなく終了した記録、pinしたguest host keyのport対応、
UTF-8 locale処理の修正前、全entry clone方式とstream再読方式の実行を混同しない。
診断時の各ソース全量snapshotは保存していないため、診断ログを最終sourceの検証に流用しない。

全入力を二回streamでhashし、属性を再読する。entryごとの内容digestを保持するため、
全属性cloneの蓄積を避ける。512 MiBと有限期限は維持する。容量全量の性能認定はしていない。
ctime/birthtimeは原本履歴、未宣言のkernel/LSM属性はsite policyの別領域として扱う。
全Linux flagsや全filesystemを今回の小さいfixtureだけで認定しない。

展開は専用tmpfsである。syncfsの成功を永続媒体・物理電断の受入と呼ばない。
本番の世代認可からの起動、永続bank、controller復旧/回収、全DEB効果、実サービスと
mount/boot、完全置換ISOは未完。変更のないAda suite・証明・旧カオス・性能campaignは実行していない。
