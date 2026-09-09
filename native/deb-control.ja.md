# 元DEBの圧縮制御アーカイブを保持するnative SDK

`Pkg_Deb_Control.Stage`は元DEBの[envelope](deb-container.ja.md)を再検査してから、
制御メンバーと通常制御ファイルを既存CASへ保存する非特権SDKである。
公開CLI、第二の導入済みDB、スクリプト実行器は追加しない。UID 0は初期段階で拒否する。

## 圧縮とtarを分けた検査

`pkg_deb_decode.c`は未改変の上流zlib/liblzma/libzstdへの小さなFFI境界である。
gzipのCRC/サイズ、xzの対応checksum、zstdに含まれるchecksumを各codecで検査する。
既定の単一streamが終わり、入力を全部消費したことを必要とする。
切断・余分な末尾・連結stream・辞書等の未対応入力を受理しない。
CRCや圧縮の整合性は供給認証ではなく、署名や元DEBの信頼判定は別に必要である。

出力は64 KiBずつ進め、全展開量32 MiB、xzのdecoder memoryとzstdのwindowを128 MiBへ制限する。
元の圧縮制御メンバーは16 MiB以下。Ada側で元メンバーのhashも再照合する。
各codecの構造体をAdaへ複製せず、Cで上流headerを使う。
[上流zlib](https://www.zlib.net/manual.html)、
[liblzma](https://tukaani.org/xz/liblzma-api/container_8h.html)、
[zstd](https://facebook.github.io/zstd/zstd_manual.html)のAPIに従う。

圧縮検査後のメモリを、圧縮filterを一つも登録していないlibarchiveへ渡す。
[libarchiveのfilter](https://manpages.debian.org/trixie/libarchive-dev/archive_read_filter.3.en.html)は
外部programへfallbackできるため、ここではcodec起動を任せない。
[tarの読取API](https://manpages.debian.org/trixie/libarchive-dev/archive_read.3.en.html)だけを使い、
展開APIは呼ばない。合成gzipのCRC不正をこの二段構成で拒否する。

## 保持するもの

V7/ustar/GNU tarの平坦な通常ファイルと、任意の一つのroot directoryを扱う。
`./`の先頭表記だけを正規化し、重複名・外部パス・子directory・link・特殊file、
PAX、ACL/xattr/sparse/flagsなどの未対応属性は拒否する。無言で一部だけ採用しない。
必須の通常`control`ファイルがない場合も拒否する。内容fieldの意味はまだ解釈しない。

通常ファイルは名前によらずCASへ保持し、名前、種別、mode、uid/gid、user/group名、mtime、
サイズと内容hashをinventoryへ保存する。原本DEBと圧縮制御メンバーのhashにも束縛する。
`preinst/postinst/prerm/postrm/config/triggers`等も元のbyte列であり、実行はしない。
個数はroot directory込みで64、通常ファイルの合計は16 MiB。
原本全体を保持するため、tarの書式や元メタデータは後で原本から再確認できる。

失敗時にinventoryは空になる。途中で完成したCAS objectは残り得るが、導入済み状態や
効果完了ではない。元DEBを再梱包せず、ファイル属性や所有権を稼働rootへ適用しない。
boottime期限を処理の区切りで確認する。同期codec/CAS/ライブラリ呼出しを強制中断する
期限ではないため、外側の実行時間・メモリ・CPU制限を必要とする。

## 検証と限界

`run_deb_control_tests.adb`を登録し、再生成可能な35合成DEBで受理と拒否を検査する。
生成元は`pkgcore/tests/make_deb_control_fixtures.py --write`、確認は同じ工具の`--check`。
原本の二重解釈を避けるため、本文の内容はraw CAS hashへ保持した後に別の意味検査へ渡す。

このSDKはlibarchiveのtar解釈を用いる観測であり、tar末尾の正規性・全tar形式の適合証明ではない。
制御fieldの独立検査、全保守script効果、data.tar、phase/trigger、catalog/WAL、
本番認可・実root/boot切替を完了したとは扱わない。C境界を含むruntimeはSPARK証明の対象外。
