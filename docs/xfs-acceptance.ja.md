# XFS受入試験

検証単位はkernel/config/xfsprogs/mkfs/geometry/rescue/toolchain/暗号化/下位ストレージ/実機/方針の正確な組である。供給元の版番号と、実際の受入結果を分離する。以下は試験仕様であり実施済み報告ではない。

|対象|受入条件|
|---|---|
|オンディスク機能|要求するCRC・逆参照・parent pointer等を通常とrescueの双方が認識し、安全に読書き・検査できる|
|能力|scrub、repair、healthmonの実API。CONFIG有効だけで認定しない|
|イベント|対象UUID/namespace/boot一致、LOST、queue overflow、未知type、collector再起動、shutdown、unmount、media/file I/O errorを試験|
|並行性|対象ごと一つのmonitor、一つのrepair authority。native自動起動との競合なし|
|scrub|終了0/2/複合error/timeout/kill/部分走査を区別。checksum検査と媒体可読性を混同しない|
|修復|隔離VMと複製データだけでfault injection。成功後の再検査、失敗/結果不明、試行上限、修復中の再中断|
|内容|正確なcatalogとfile digest/属性/設定を照合。metadata正常で内容が誤っている場合を拒否|
|容量|データ/metadata/inode、WAL、証拠、回復用領域の予算。満杯時に古い証拠を無断削除しない|
|電源断|更新と逆順復旧の各永続化境界、fsyncエラー、デバイス喪失、二次故障|
|起動|暗号鍵登録、全ESP、正常UKI/rescue、root/catalog/control/trustの対応、未知featureの安全な拒否|
|クラスタ|旧writer隔離、バックアップ・複製の整合性、保守中の追加故障、破損伝播|

故障注入は本番・利用中ディスクで実施しない。生の強制修復コマンドを回帰テストに含めない。原本を保全した隔離環境と、停止可能な複製データを用いる。実装から生成する証拠は入力/実行ファイル/環境のダイジェストに束縛する。

Niaの全体出荷には、このFS固有条件に加え、[出荷条件](../contracts/release-gates.json)が必要である。
