# 実設定のsnapshot

`Pkg_Conffile_Snapshot`は設定更新判断へ渡す現在内容を実ファイルから保存する内部SDKである。
判断ADR-0096。既存の開いたStoreと、controllerが選択したrootの借用directory FDを受ける。
独立した導入済みDBや公開コマンドを増やさない。

## 観測と保存

pathはroot内の絶対byte名で、Unicode正規化やASCIIへの変換をしない。最大4096 bytes、
128 component、各255 bytes。空component、dot/dotdot、末尾slash、NULを拒否する。
rootと各既存祖先はrootまたは実行user所有で、group/otherから書込不可のdirectoryを要求する。
openat2のBENEATH/NO_SYMLINKS/NO_MAGICLINKS/NO_XDEVを使い、mountを越えない。
別mountやsymlinkを必要とする構成は別の明示的なnamespace計画が必要である。
実在する祖先を通過した後のENOENTだけを欠落として保持する。permission/IO/未対応を欠落にしない。

末尾をO_PATHで観測し、通常fileだけを自身のprocfs FD参照から再openする。
名前を再openして別種inodeを読まない。複製後のinode/mount/deviceも一致確認する。
O_NOATIMEで読取自身によるatime変更を避け、取得権限がない場合は拒否する。
mtime/ctime/atime/btimeの符号とnanosecond、mode全bit、UID/GID、link数、statx属性maskと値、
FS_IOC_GETFLAGS、可視xattrの名前/valueを保持する。可視ACLは元のsystem xattrとして保持する。
取得未対応を勝手にzeroへ置換しない。btimeだけはkernelの明示的な有無を保持する。

同じinodeの属性を内容hashの前後で比較し、rootからも再openして比較する。
内容は64 KiB単位で既存CAS Writerへ保存し、WriterのSHA-256検証を通す。
版付きmetadataも保存した後、もう一度namespace/内容/属性を読み直す。
成功時だけCurrentとmetadata hashを返す。空fileは実SHA-256を持ち、Missingは内容hashがzeroである。
失敗時はsnapshotを閉じ、CurrentをOther、metadata hashをzeroにする。保存済み未参照objectは残り得る。

## 観測record NIACOBS1

全整数は8-byte little endian。timestampのsecondsは符号付き64-bitのtwo's-complement、nsecは非負整数。
これは観測recordであり、root archiveへ直接展開する復元形式ではない。

|順序|フィールド|
|---|---|
|header|8 bytes `NIACOBS1`、path長、raw path、実効UID、実効GID|
|各既存directory|tag 2、identity|
|欠落|tag 0、先頭slashを除いたpath中の欠落component開始byte offset|
|通常file|tag 1、identity、nlink、size、statx attributes、attributes_mask、atime、mtime、ctime、btime有無、有ならbtime、inode flags|
|通常fileのxattr|個数、名前長/raw名前/value長/raw値の反復。名前のunsigned byte順|
|末尾|内容SHA-256の32 bytes。欠落だけzero|

identityはmount ID、device major/minor、inode、mode、UID、GIDの順。
directoryの時刻やlink数は子の増減でも変わるためnamespace identityには入れない。
record最大192 KiB、xattr名/value合計128 KiB。file上限はcaller指定かつ8 GiB以下。
BOOTTIMEの排他的期限を各読取/属性処理間に確認するが、停止したfilesystem syscall自体の
強制終了保証ではない。配備側にも有限なworker lifecycleが必要である。

## 接続上の条件

Snapshotはroot FDを複製して所有する。callerのFDは閉じない。
Storeはsnapshot存続中ずっと同じopen予約を保持する。Recheckは予約FDの一致を要求し、
rootから現在の内容とmetadataを読み直す。Storeのclose/reopenやFD再利用を許可するAPIではない。
選択したrootと稼働世代の一致、全managed予約と最終再照合はcontrollerの義務として残る。

CAS排他は管理者のeditorや特権writerを凍結しない。statx自体もatomicな全属性snapshotを保証しない。
この処理は観測できた変更を検知するもので、悪意のある特権writerとの完全な競合防止証明ではない。
一般userから隠されたxattrは完全性を主張できないため、観測credentialを記録する。
特権属性observer、root所有private設定の読取、利用者選択への束縛、退避名衝突・保持閉包、
hardlink/symlinkの適用、全属性の復元形式と実root公開は引き続き未完である。

Linuxの挙動は[openat2](https://man7.org/linux/man-pages/man2/openat2.2.html)と
[statx](https://man7.org/linux/man-pages/man2/statx.2.html)の上流man-pagesを参照する。
