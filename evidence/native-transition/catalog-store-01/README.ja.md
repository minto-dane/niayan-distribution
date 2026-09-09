# 正規catalog保存の検証

`Pkg_Catalog_Store`は既存NIACSEL1の正規byte列を同じCASへ保存し、元DEBから
catalogとpayload indexを再構築する。対象sourceと結果は`report.json`、全保存ファイルは
`SHA256SUMS`で確認する。導入済みDBやaccepted generationのポインターを追加していない。

4合成原本の保存・再open・再構築、全identity/関係/claim保持、20形式不正、空payload原本欠落、
catalog欠落、期限と旧成功出力の消去を検査する。元DEBを独立したar/tar readerで読み、
単純なregular payloadの全属性からindexを計算して、保存frameと全metadataへ照合する。

正規frameは440 byte、アドレスは
`89a31cbefdb7297293dc8b7a7315adfadccc79dcaffc580e5ac254d9610ee44f`。
以前のselected-catalog工程のfingerprintと一致し、hash形式を変更していない。
`catalog.bin`はこのアドレスに一致する正規frameである。
通常の生成CI runnerでも独立oracleがその実行のCASを直接読み、byte列を照合する。
`accepted-oracle-summary.json`はその実行logから保存した結果。
`attempts/debug-oracle.json`は先行診断実行の詳細で、frameのアドレスを通常CIと照合する。

`attempts/`には初期Ada試験driverの構文・演算子可視性のコンパイル失敗を保存する。
診断実行を全体qualificationの代わりにせず、最終sourceの全build/testを別途実行する。
固定環境で全source・4アプリ・25 Ada main、新320 assertionsが成功した。
29実行ファイルは独立二ビルドでbyte一致し、724入力をcheckout・通常・独立・sanitizedの全コピーへ照合した。
29 ELFの緩和設定、8本のroot拒否driver（新7 assertions）、ASan/UBSanリンク下320 assertionsも成功。
ソース24工程は成功し、前後subjectは`cc7c7d9b771e5a9b784d0a926f52eb04ee5924eb73c82997c8fbd7ed98f364af`で一致した。
ASan/UBSanはC境界とallocator/library callの検査で、Adaと上流library本体は非計測、leak検査は無効。
既存7repoの証明入力はexact membershipとhashが不変、新runtimeはSPARK対象外である。

全OS原本集合・最大容量・供給認証・accepted generationとの同一reservation下照合・
CAS pin閉包・依存/実phase/全効果/所有権・実root/boot・完全置換ISOは未受入。
同期CASの全hash処理には外側timeoutも必要。保存・再読込の成功は実行許可ではない。
