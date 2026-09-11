# 設定entryのPAX出力

`Pkg_Tar_Output`は通常設定fileのPAX/header prefixを生成する内部codecである。判断ADR-0101。
root全体の組立てや実属性適用はまだ接続していない。

固定環境のlibarchive 3.7.4に、mtime=(-42,123456789)、ctime=(-1,1)、birthtime=(0,42)を
与えてPAX出力したところ、負の小数時刻はそれぞれ-42.123456789/-1.000000001となり、
指定したbirthtimeも出力されなかった。これをそのまま設定世代の出力に使わない。
対象入力・PAX bytesと独立Decimal比較はconfigured-tar-01のwriter-probeに保持する。
この観測を他版や全birthtimeの場合へ一般化しない。上流ソースのコピーや変更は行っていない。

## 出力の契約

Startへroot相対のraw path、全permission bit、数値UID/GID、内容サイズと4時刻を渡す。
mtimeは必須。空path、絶対path、NUL、空/./.. component、file種別を含むmodeを拒否する。
pathは最大4,096 byte、内容サイズは既存CASの上限まで。中身を読まず、指定したサイズの真正性は判断しない。

Add_Xattrはraw名とraw値を受け、名前をpercent encoding、値をpaddingなしbase64として
LIBARCHIVE.xattrへ出力する。固定環境ではSCHILY.xattrのpercent encodingが読取時に戻らないことを
確認したため、新規のraw属性出力にはLIBARCHIVE形式を使う。空値も実読戻しで確認した。
既存SCHILY入力の解釈は変更しない。
Add_Extensionは検査済みのSCHILY/既存LIBARCHIVE fieldをbyte列で加える。全keyは重複なく昇順で出力する。
予約済みのpath/size/owner/clockをextensionで上書きできず、失敗するとbuilderを消す。
これは属性の効果を解釈・認可するAPIではない。無効なACL/flags等は既存の意味readerで拒否する必要がある。

FinishはPAX header、拡張fieldとzero padding、通常file headerを返してbuilderを消費する。
呼出し側が続けて正確な内容サイズのbytes、その512 byte境界までのzero paddingを加える。
archive末尾には最後に1,024 byte以上のzero終端を付ける。prefixだけを完成tarと呼ばない。
短い出力bufferや失敗ではUsed=0と全zero出力になり、部分headerを成功として返さない。

## 名前・数値・時刻

PAXはhdrcharset=BINARYを明示し、表示localeでファイル名を変換しない。
上流の[BINARYとxattrheader optionの仕様](https://manpages.debian.org/trixie/libarchive-dev/archive_write_set_options.3.en.html)も参照。
uid/gid/sizeはPAXの十進数で保持し、古いtar数値fieldの幅に切り詰めない。
現行のxattr名上限255 byteがすべてpercent encodingされても読めるよう、key上限を782 byteとした。
LIBARCHIVE形式ではdecoded名の255 byte/NUL/percent encodingとbase64の文字/長さ/padding bitを検査する。
全PAX拡張の既存の個別/総量制限は維持する。BINARY以外の新しいcharset宣言を推測して受けない。

POSIX timespecはfloor秒と非負の小数部分を持つため、負の十進表記とは変換が必要である。
(-42,123456789)は-41.876543211、(-1,1)は-0.999999999になる。
符号付き64 bit最小値も絶対値へ反転せず文字列化し、存在するbirthtimeは明示的に出力する。
readerも負の累積で全signed範囲を検査し、最小値を超える負の小数や最大値超過を受けない。
clocks、raw name、空/バイナリxattr、ACLとflagsの出力をnative framingと独立Pythonで照合する。
scriptなしDEBへ包んで既存payload readerにも戻し、属性/内容/元原本hashを検査する。

## 残る接続

Root_Configurationの元claimを直接コピーし、設定entryの完全元属性からこのcodecへ渡すadapterと、
全rootのstream/CAS保存・保持閉包・最終再確認はまだ必要である。
localの生ACLとarchive ACL、inode flagsと適用可能flag、ACL/capabilityとchown/chmodの相互作用も
別の適用方針を必要とする。ctime/birthtimeを記録できることを実filesystemで設定可能とみなさない。
全inode効果、全managed認可、特権observer、世代保持/復旧・実root/bootと公開の要件は継続する。

さらに同じ固定upstream readerは、正しい-41.876543211を(-41,876543211)として返した。
Pkg_Deb_Payloadはnative framingの値で補正しており今回の相互読戻しも成功したが、
root_extract.cは現在upstreamのentry時刻を直接使うため、実適用にはnative時刻への補正が必要である。
reader-time-probe.logに実値を保持した。旧workerの自己読取/自己比較を負の小数時刻の正しさの根拠にしない。

## 保存属性adapter

`Pkg_Configuration_Entry.Prepare`はFile_Effectから元NIACOBS1またはDEBを読み直し、
検証した内容のsizeと通常file header prefixのCAS digestを返す。
source pathとtarget pathを区別するので、backupも元属性を維持する。
mode/UID/GIDのassertionと内容hashを原本へ照合し、vendor permission overrideは同じsource pathの
保存ローカル観測へ束縛する。ACLのowner/mask（なければgroup）/otherを数値modeと整合させ、named権限は残す。
raw POSIX access ACLはsemantic属性に変換し、raw名・空/binary xattrと4時刻は保存する。
ACLの数値identityを使い、元の表示名は保存原本だけに残す。

表現範囲外のnamed ACL ID、regularのdefault ACL、vendor raw ACLの重複表現、未知のactive statx属性、
往復一致しないflags、ローカルnlink>1はUnsupportedとなる。extent配置bitは原本観測として保持し、
移送先へsetする振舞いの指定とはしない。ローカルにない既知の振舞いflagは明示clearする。
失敗時digest/sizeを消す。完了済みの未参照CAS objectが残る場合はある。

このAPIは保存済み属性の変換だけである。全root stream、content/padding/終端、prefixを含む保持閉包、
選択のlive再検証と本番認可はcaller側で接続する必要がある。SDKにUID0権限を追加しない。
ctime/birthtimeは履歴であり、任意の実FS復元を意味しない。判断はADR-0104。
