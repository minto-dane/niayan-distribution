# Catalog由来のCAS保持閉包の検証

対象と結果は`report.json`と`source-checks/report.json`に固定する。
仕様は[保持閉包](../../../native/catalog-retention.ja.md)、判断はADR-0073。
新しいPrepare/Verify/Pin/Verify_Pinと、従来catalog保存・現世代観測を含む全25 Ada mainを固定環境で検査する。

二catalog・五合成原本について独立readerが原本/control/data/内容/属性の正確な集合、
正規マニフェストbyte列、CAS実内容とpinを照合する。
通常の21 objects/752 byteと追加の15 objects/560 byteを対象とする。
35不正一覧、21掲載objectの個別欠落、破損、pin衝突/再open、明示再構築、期限とUID0を検査する。
scriptやdeviceは内容の観測のみであり実行・展開しない。

新規build treeの二独立build、29実行ファイルと全729入力の比較を行う。
ASan/UBSanはC境界とallocator/library呼出しの検出範囲で、Ada・上流library本体は非計測、leak検査は無効。
さらに新規workspaceで全7repoのcompile-all・18アプリ・登録済み71 Ada main、
全体source/reference検査と私有D-Busを実行する。18アプリは別workspaceでの独立buildとも比較する。
全体検査runnerは子の環境からSOURCE_DATE_EPOCHとTZを除く。二回目は固定epoch・変更mtimeとTZを渡す。
実際の環境差をworkspace-reproducibility.jsonへ記録し、二回とも同じ環境を渡したとしない。
全7repoのproof入力が不変であることを確認する。新規runtimeはSPARK対象外。
初回診断のByte演算子可視性のコンパイル失敗は修正し、新規treeで再検査した。
workspace初回検査は、コピーから除外した過去の証跡文書へのリンクが欠けていたためbuild前に停止した。
参照先6文書を原本のままコピーし、入力hashを記録して再検査した。検査条件は弱めていない。
次の全体実行では既存の世代公開試験が相対媒体pathをabsolute-onlyのFS SDKへ渡して失敗した。
driverでFull_Nameへ変換し、新規build treeで全体検査をやり直した。実行時FSの条件は変更していない。
修正後は全116工程と71 Ada main、私有D-Busの32+10試験が成功した。Python単体試験は580件発見・
source実行時11件skipであり、skipを実行成功に数えない。私有D-Busは別の42件実行として記録する。

`reference-snapshot/`は最終診断の二closureと参照先、pinの小さな支持データ。
通常CIの独立oracleと同じbyte集合を比較しており、実OSのroot snapshotではない。
`SHA256SUMS`が全支持ファイルを束縛する。ソースsubjectと残る条件はreportを参照する。
全OS/最大容量、世代・効果・認証・復旧rootを含む保持と安全なGC、本番admission・実root/bootは未受入。

最後に更新したAGENTS.mdとSTATUS.ja.mdだけの差分hashはhandoff-only-changes.jsonに記録した。
これらはengineering source subjectと実行ファイルのbuild入力の対象外である。
