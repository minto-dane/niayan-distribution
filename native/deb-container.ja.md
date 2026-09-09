# 元DEBをnative CASへ取り込む読取SDK

`pkgcore/runtime/pkg_deb_container.*`は、既存MC_Storeに保存した元DEBのar envelopeを
独立に検査する内部SDKである。Python、apt、dpkg、外部展開コマンドは呼ばない。
公開管理入口や別の導入済みDBを作らず、ファイルをrootへ展開しない。

`Inspect`は元DEBのhashをCASで再検査した後、ar magic、60 byte header、
数値と名前、サイズ、順序、LF paddingを検査する。検査時に読んだ全バイト列のhashも
元DEBと照合する。各メンバーの名前・種別・圧縮ラベル・位置・サイズ・header hash・
内容hashと、原本全体のhash・サイズ・minor版を返す。失敗時に部分結果は返さない。

`Stage_Member`は原本を開き直して全envelopeを再計算し、引数の全項目と照合する。
一致したメンバーだけを64 KiBずつ既存CAS writerへ渡す。writerがサイズとhashを
確定するまで成功digestは返さない。失敗した未完writerは破棄する。
原本や既に完成したCAS objectは保存失敗で取り消さない。これらは導入済み状態ではない。

## 受理するenvelopeと境界

先頭の`debian-binary`はmajor 2と数値minor、LF終端を必要とする。
追加の印刷可能ASCII行も原本に保持する。制御アーカイブとデータアーカイブを順序どおり
必要とする。必要メンバー間の`_`で始まる拡張とデータ後の拡張をhashへ保持する。
名前はASCII英数字と`_-.`、ar末尾の任意の`/`に限定する。重複や長名tableは拒否する。
制御側はtar/gzip/xz/zstd、データ側はさらにbzip2/lzmaのラベルを識別する。
これは圧縮ストリームやtar内容が有効という判定ではない。
形式の根拠は[Debian 13のdeb(5)](https://manpages.debian.org/trixie/dpkg-dev/deb.5.en.html)。

上限は原本8 GiB、圧縮された制御メンバー16 MiB、16メンバー、版情報256 byte。
データの展開後上限やtarメンバー制約は後続読取器が別途課す必要がある。
UID 0の呼出しは初期化前でも拒否する。CAS ownerとwriterの予約条件はMC_FS/MC_Storeと同じ。
前後のinode・size・mtime・ctime等を比較するが、悪意あるrootに対する隔離証明ではない。

boottimeの期限を読取りと保存の区切りで確認する。最初のCAS全体hashや同期I/Oを
この期限だけで強制中断することはできない。外側の実行時間・メモリ・CPU制限が必要である。
本番helperへの転用、署名信頼、control・tar・全DEB効果、導入済みcatalog、実root公開は未完。

## 検証

`pkgcore/tests/run_deb_container_tests.adb`を共有test-planへ登録した。
合成した不正envelope、切断全位置、コードラベルと拡張の保持、偽の位置とhash、
複数chunk、空メンバー、期限とCAS破損を検査する。合成内容はtarではなくopaque byte列である。
同じ非公開test mainへCAS・媒体directory・filenameの3引数を渡すと、実DEBを取り込み、
全メンバーを保存し、照合用のhash・位置・サイズを出力する。配布アプリではない。
UID 0の別contextでは二つのSDK入口が初期化前に拒否されることだけを確認する。

実行証跡は`evidence/native-transition/deb-container-01/`へ保存する。
新runtimeはSPARK証明の対象外であり、既存全7repoの数理入力の不変照合と区別する。
