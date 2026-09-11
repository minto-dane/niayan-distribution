# 元DEBのファイル内容と属性を保持するSDK

`Pkg_Deb_Payload.Stage`は元DEBのenvelopeとdata streamを再検査し、tarのエントリを
privateなinventoryへ保持する。通常ファイル、空ファイル、directory、symlink、hardlink、
character/block deviceとFIFOを観測する。ファイルを展開・作成する権限ではない。
UID 0を拒否し、既存CASを用いる。公開コマンドや導入済みDBは追加しない。

## 原本と属性

原本DEBと展開tarをCASに保持し、成功したinventoryを両digestへ束縛する。
通常ファイルの全内容をlibarchive経由でhash化してから、検査済みtarの同じ範囲を
64 KiBずつCAS writerへ渡して再照合する。symlinkの文字列もCASへ保持する。
空ファイルと未保存digestは区別する。途中失敗ではinventoryを公開せず、
既に完成したCAS blobも導入済み状態にはならない。

採用profileのmode下位12 bit、32 bit UID/GID、user/group名、4種の時刻、
POSIX ACL、xattr、inode flagとdevice major/minorを保持する。
時刻は符号付き秒と0〜999,999,999 nanosecondへ正規化し、PAXの負の小数も正確に扱う。
時刻の書換権限や、ctime/birthtimeを通常APIで復元できることを意味しない。
ACLで表現される基本permissionは上流entryのmodeへ反映される。元headerはtarに残る。

xattrは名前をbyte順に整列した既存形式（U16件数、U16名前長、U32値長、名前、値）でCASへ保存する。
`security.capability`もbyte列として保持するが、このSDKでは付与しない。
ACLはU16件数に続き、U32 type/permission/tag/qualifier、U16名前長と名前を保持する。
整数はbig endian、qualifierの未指定値は0xffffffff。上流iteratorの順序を維持する。
ACLとflagを独自に削除して既存の世代形式へ適合させない。

## パス、リンク、文字コード

pathとhardlink先は先頭`./`を除き、directory末尾`/`とrootを正規化する。
絶対path、空component、`.`/`..`component、255 byte超component、重複、
宣言された非directory祖先を拒否する。symlinkの文字列は保存し、仮想rootから
字句的に外れる参照を拒否する。絶対symlinkは対象世代内の参照として保持する。
参照先が未存在のsymlinkを許す。hardlinkは全エントリ読取後に解決し、前方参照・chainを扱い、
cycle・欠落・通常ファイル以外への参照を拒否する。inode番号はinventory内の参照である。
複数packageを合成した後のancestor・所有権競合・symlink経由の解決は別途必要である。

出力名にはASCII専用の`MC_Text`を使わず、有界byte stringを使う。
libarchiveの文字コード変換はthread-localな固定`C.UTF-8`で行い、呼出側localeを復元する。
globalな`setlocale`はSDKから呼ばない。試験の表示protocolは名前をhex化する。
local PAXの名前は原本byteを独立に保持し、ライブラリによるUnicode正規化後の名前で置換しない。
非表示文字を含む名前の観測成功は、端末へ未処理で表示する許可ではない。

## framingと対応範囲

`Pkg_Tar_Framing`が512 byte header、unsigned checksum、sizeとPAX上書き、
zero padding、2 block以上の終端と残り全zeroを検査する。
上流readerの各entryの開始位置・サイズと独立のframing位置を一致させる。
USTAR、GNU longname/longlink・正のbase256数値、採用したlocal PAXを扱う。
GNUとPAXの混在extension、同種local extensionの反復、global PAX、sparse、
NFS4 ACL、未知PAX key、非対応type、未知flag、signed checksumを未対応として拒否する。
固定上流はglobal PAXを適用せず、負の小数時刻にも異なる解釈があるため、黙認しない。
POSIX access/default ACLは明示したuser/group/mask/otherとrwx三桁の構文を検査する。
ACL名はASCIIの採用profileに限る。PAX keyの重複と空の名前上書きも未対応として拒否する。
拡張ACLの全方言・全tar形式を実装済みとはしない。

上限はtar 8 GiB、131,072エントリ、各名4,096 byte、名前総計64 MiB、
extension 1 MiB/個・64 MiB合計、xattr 64件/entry・値65,536 byte、
xattr/ACL blob 131,072 byte、ACL 1,024件。小数9桁を超える非zero精度は拒否する。
PAX時刻の整数絶対値は2^63−1まで。同期I/Oと上流呼出しを制限する外側期限と資源scopeが必要。

上流仕様と挙動の確認元は[libarchive 3.7.4 tar実装](https://github.com/libarchive/libarchive/blob/v3.7.4/libarchive/archive_read_support_format_tar.c)、
[entry ACL API](https://manpages.debian.org/trixie/libarchive-dev/archive_entry_acl.3.en.html)、
[thread locale API](https://manpages.debian.org/trixie/manpages-dev/uselocale.3.en.html)。上流ソースは改変しない。

## 世代への接続と検証

既存の世代v1 file planはhardlink・setuid/setgid/sticky・特殊file・全時刻を表現できない。
このinventoryの情報を切り落として渡すことは禁止する。versionを持つ世代形式と実行器、
所有権・効果・catalog・認可・実root/bootへの接続は引き続き未完である。
新runtimeはSPARK対象外であり、既存proofの成功を新経路の証明へ流用しない。

`run_deb_payload_tests.adb`がprivate CASで通し試験を行う。
`make_deb_payload_fixtures.py`は合成DEBを再生成し、`compare_deb_payload.py`は
Debian読取工具・Python tarfile・CASの全hashによる独立oracleを提供する。
このoracleは試験工具であり、展開やインストールを行わない。

## access ACLの実効mode

access ACLにmaskがあるとき、数値modeのgroup classはmaskのpermissionを使う。
上流archive entryが持つgroup-owner permissionは元ACL blobへそのまま残す。
これは別の値であり、modeを直すためにarchive entry自体を変更してはならない。
ADR-0104でSDK読取りと実展開workerのstat照合を修正した。
従来の誤ったmodeを含む派生metadataは再観測時に異なる。既存hashや原本の書換え、
旧計画の暗黙移行は行わない。対象旧計画の移行・復旧は別途受入が必要である。
