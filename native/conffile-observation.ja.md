# 保存した設定属性の読戻し

`Pkg_Conffile_Observation.Load`は、保持済みNIACOBS1をlive snapshot handleなしで解釈する。
元形式は[実設定snapshot](conffile-snapshot.ja.md)、判断はADR-0098。
既存Storeからmetadataを再hashし、期待したraw pathと照合する。
通常fileの場合は参照先の内容objectも再hashし、記録サイズとの一致を確認する。
host pathを開く処理や欠損objectの再生成は行わない。

## 検査と公開する値

最大192 KiB、128 component、path 4096 bytes、component 255 bytesの元形式上限を維持する。
全fieldの境界、directoryの数/種別/保護mode/記録上の所有者と同一mount/device、
欠落componentの開始位置、通常fileの種別/link数/サイズを検査する。
UID/GIDなど32-bit fieldの過大値を切り詰めず拒否する。timestampはsigned 64-bitとnanosecondを保ち、
birthtimeの不在とzero時刻を区別する。statxの値はmask内に収まる必要があるが、未知のmask/flag bitは保持する。
デコード可能であることと、そのflagを物理fileへ設定できることは別である。

|取得値|意味|
|---|---|
|Path / Address|正確なraw pathと検査したmetadataのCAS hash|
|Image|MissingまたはRegularと実内容hash。無効な記録はOther|
|Attributes|inode/mount/device、全mode bit、UID/GID、link数、サイズ、statx値/mask、inode flags、四時刻|
|Observer_UID / Observer_GID|記録された実効ID。独立した本人確認ではない|
|Read_Directory|rootを先頭にした各既存祖先のidentity|
|Missing_Component|欠落の1起点component番号。regular/無効時は0|
|Read_Xattr|昇順のraw名と元value bytes。短い出力bufferでは部分結果を返さない|

xattrは最大32768件、名前255 bytes、各値64 KiB、名前/value合計128 KiBで、
元listxattrの名前列64 KiB上限も確認する。空名、NUL名、重複/順序違反を拒否し、
空の値と不在を区別する。Linuxの可視POSIX ACLは`system.posix_acl_access`の元byte列のまま保持し、
archive内のsymbolic ACLと同一形式として扱わない。recordの切断や余剰byteも拒否する。

snapshot保存側もこのreaderを呼び、Cの内容/サイズとCAS読戻し結果の一致を確認してから返す。
失敗時はsnapshot/readerの部分状態を消す。metadataを読むだけで現在のfileが不変とは判断しない。

## root適用へ必要な判断

Debian 13の保持済みdpkg 1.22.22 sourceでは、新しいconffileに既存fileの所有者とpermissionを
引き継ぐ処理を確認した。対象source/member hashはこの工程の`upstream-source.json`へ記録した。
そのため、新vendorの内容を採用する場合にも、属性をすべてvendor値へ置換するとは限らない。
これは上流処理の確認であり、Niaの全属性適用方針や実rootの更新受入ではない。
参照先は[Debianのsource package](https://packages.debian.org/source/trixie/dpkg)。

今後、既存所有/permission、vendorの全属性、localの可視属性と利用者選択を、明示的な採用方針へ
結び付ける必要がある。inode/link関係、ctime/birthtime、filesystem固有flagはそのまま復元可能とは限らない。
特権属性の完全観測、全namespaceとroot archiveへの反映、認証UI/managed admission、
世代保持/復旧とbootは未完。このreaderの成功をそれらの許可・完全性に読み替えない。
