# 元DEBのnative読取SDK検証

対象source subjectと結果は[report.json](report.json)。
固定開発コンテナでpkgcore全ソース、4アプリ、15 Ada test mainが成功した。
新読取器は764 assertions、別root contextで二つのSDK入口の初期拒否を確認した。
19実行ファイルが異なる作業パス・入力mtime・タイムゾーンの新規ビルド間で一致した。
[346入力](pkgcore-inputs.json)は両ビルドと最終checkoutで照合している。

保存済み実DEB 7個の元データと全21メンバーを、独立したar工具とCAS保存後に照合した。
原本のhistorical hashとサイズは[入力記録](original-media-inputs.json)で固定する。
内蔵test mainと照合用[スクリプト](compare-real.py)は資格試験専用で、導入器ではない。
CAS directoryはメンバーごとの検査終了後に破棄し、原本は読取専用で保持した。

最初の試行では試験台帳の生成順、追加testの構文、試験fixtureのCASパスに誤りがあった。
失敗ログはattemptsへ保持し、成功結果と混ぜない。最終成功は専用のfresh buildに束縛する。

[既存の全7proof入力](proof-input-comparison.json)は不変であり、同じ証明は再実行していない。
新しいruntimeのSPARK証明は行っていない。
重い工具は順番に3 GiB・swap 0・CPU 1コア分・128プロセスのkernel制限下で実行した。
root拒否以外のコンテナ実行はUID 1000、全実行はネットワークなし。

検証範囲はar envelope、元DEBと圧縮メンバーの正確なCAS保存である。
tarの内容・制御意味・署名認証・導入効果・稼働catalog・実root/boot切替・電源断は未受入。
[SDK設計](../../../native/deb-container.ja.md)を参照。
