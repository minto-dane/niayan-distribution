# 元DEBのdataメンバーをstreamで保持するSDK

`Pkg_Deb_Data_Stream.Stage`は元DEBのdataメンバーとその展開byteを既存CASへ保持する。
`Pkg_Deb_Container.Stage_Member`でenvelope全体を独立に再検査し、原本へ対応したメンバーを使う。
UID 0を拒否し、原本を修正しない。

## 増分処理と保存

小さなC境界は無圧縮・gzip・bzip2・LZMA-alone・xz・zstdを扱う。
上流libraryを改変せず、C境界自身はファイル・プロセスを操作しない。
各stepは入力・出力最大64 KiBを借り、呼出し後にはcaller bufferを保持しない。
完了・失敗後のdecoderは再開できず、破棄する。

最初のpassは圧縮元と展開物の全hash・サイズを求める。
二度目は原本byteを再照合して同じ展開結果を既存CAS writerへ渡す。
全出力を一時メモリへ確保せず、未知のdigestでCAS契約を弱めない。
入力descriptorの属性は前後で照合し、二度目のhashとサイズも一致を要求する。
CASへ保存されたblobは稼働状態の公開ではない。

## 上限と形式

入力と展開物は既存CASの8 GiB上限内で、呼出側はさらに展開量の上限を指定する。
xzとLZMA-aloneのdecoderメモリは128 MiB、zstd windowは128 MiB。
bzip2は上流形式のblock上限に従う。deadlineは各I/Oとstepの前後で確認する。
同期I/O・library呼出し・元CAS全hashの間も制限する外側process期限と資源scopeが必要である。
CPUとCAS容量の予約はこのSDK単独では成立しない。

各codecの完全な終端と全入力消費を要求し、連結stream・trailing byte・切断・不正checksumを拒否する。
LZMA-alone自体にはchecksumがなく、展開成功を供給認証とは扱わない。
仕様の根拠は[zlib](https://zlib.net/manual.html)、[liblzma](https://tukaani.org/xz/liblzma-api/container_8h.html)、
[zstd](https://facebook.github.io/zstd/zstd_manual.html)の増分APIと固定環境のheadersである。
将来の形式拡張を無断で解釈せず、現profile以外は失敗させる。

## tarと導入の境界

この結果は展開byteの観測であり、まだtar entryの検査や抽出ではない。
path、hardlink/symlink、所有権、ACL/xattr、sparse、特殊file、生成効果、
導入済みcatalog・認可・実root/bootへの接続は別の工程で実装する。
関係項目や制御情報の検証も単独のdata stream保存からは推論しない。
新Ada/C runtimeはSPARK対象外で、実行検証と独立レビューが必要である。

試験は`pkgcore/tests/run_deb_data_stream_tests.adb`、fixture生成は
`pkgcore/tests/make_deb_data_fixtures.py`。証跡は`evidence/native-transition/deb-data-stream-01/`へ保存する。
