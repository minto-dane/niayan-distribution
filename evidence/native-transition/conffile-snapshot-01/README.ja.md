# 実設定snapshotの受入

対象source subject: `d639aed02b6583e79580f3a10e43094af0fd05b1088ac4b5333bc8ac6597a913`。

Debian 13固定開発container、非root、私有root/CASで実行した。
`test-03.log`の強制再compile、Ada 41 assertionとASan/UBSan付きC検査を最終受入とする。374 compile入力と3 C入力を実workspaceと照合した。
ELFは`artifacts.json`にhashを保存し、配布物への組込みや本番認定にはしない。

内容・inode置換・削除・祖先欠落/作成・mode/xattr/実POSIX ACL/link数、非UTF-8/空白名、
負/小数時刻・atime非変更、権限不足、期限、空fileと複数chunkのCAS保存を検査した。
C追加試験の途中で、ACL後の0640へ同値chmodする誤ったfixtureが失敗した。
`c-final.log`はその失敗、`c-accepted.log`は実変更へ修正した後の受入であり、上書きしていない。
初期compile/testログは開発過程であり、最終source受入は`test-03.log`を使う。

source構造・link/lint・生成CI・license検査も成功。数学的入力と共有vendorは不変で、
全suite・証明・旧カオス・VMは繰り返していない。3 GiB/swap0/CPU1/pids128を維持した。
秘密鍵、実設定、CAS、ELF、core dumpやVM diskはこの証跡に含めない。

隠れた属性namespaceを完全観測したという意味ではない。
特権observer、controllerでのroot/予約の束縛、利用者選択・退避衝突・保持閉包・
全root復元/公開、boot、全DEB効果、完全置換ISOと全言語翻訳は未完。
