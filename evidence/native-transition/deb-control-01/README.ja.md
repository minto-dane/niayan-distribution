# 圧縮制御アーカイブ読取SDKの検証

対象source subjectと結果は[report.json](report.json)。
固定Debian 13開発コンテナでpkgcore全ソース、4アプリ、16 Ada mainを検査した。
新しい制御読取器は35合成DEB・229 assertions。元envelope読取器764 assertionsも含む。
合成fixtureは上流tar/compressorで再生成し、元の全byte列とmanifestが一致した。

二つの独立した作業パス・入力mtime・TZのビルドで20実行ファイルを比較した。
最終test driverは共有runnerの相対fixture引数も受けられるようにし、両作業ディレクトリで
再コンパイルした。[387入力](pkgcore-inputs.json)は両ビルド・sanitizer用コピー・最終checkoutと照合する。
最初のfull buildログと最終再検査ログを区別して保存する。

C境界をASan/UBSanで計測して、同じ229 assertionsを実行した。
計測範囲は小さなC境界で、Adaと上流の共有library自体は計測していない。
leak検査は無効であり、リーク不存在の証明ではない。設定は[実行条件](commands.json)。
通常の20 ELFはPIE、非実行stack、RELRO、即時binding、非RWX LOADを検査した。
別root contextでは元envelopeの二入口と制御読取の一入口の初期拒否を検査する。

保存済み7コンポーネントDEBと、以前の開発cacheにある6個の上流DEBを比較した。
計13原本・65制御entryのbyte列とmode/uid/gid/mtimeを独立ar/Python tar読取およびCASで照合する。
元の輸送filenameに含まれる`~`と`%`は既存MC_FS内部pathの対象外のため、二つのfixtureは
中立な別名でコピーした。元filenameと元のbyte hashは[入力記録](original-media-inputs.json)へ残す。
SDK自体はCAS digestを受け、輸送filenameを公開管理コマンドへ追加していない。
元データを再梱包せず、制御scriptを実行していない。これは新しい供給認証ではない。

初期試験では相対fixture pathの前提違いを検出した。また、libarchiveだけではgzipのCRC不正が
拒否されなかったため、上流codecで完全なstream検査をする構成へ修正した。
失敗ログはattemptsへ保持し、試験の拒否条件を削除していない。

C境界もcanonical索引へ追加し、直接のcodec開発依存を共有CIに明記した。
[既存proof入力](proof-input-comparison.json)は全7repoで不変。
新runtimeをSPARK証明済みとは扱わない。すべての重い工程は順番に、3 GiB・swap 0・
CPU 1コア分・128プロセスのkernel制限下で実行した。

全tar形式・制御fieldの意味・保守script効果、data.tarと全DEB意味、稼働catalog/WAL、
実root/bootと電源断、完全置換ISO、全言語翻訳と応答互換性は引き続き未完。
[実装範囲](../../../native/deb-control.ja.md)を参照。
