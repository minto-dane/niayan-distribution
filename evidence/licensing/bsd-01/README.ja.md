# BSD 3-Clause統一と新しいsource profileの確認

現行の対象subjectは`4267f3a6f8668bcfb1283c270fbeaa04b9e97d81bb2095b67bdc9aec32ed4643`。
利用者の指定に従い、9 repositoryの現在の自作コード・説明をBSD-3-Clauseへ統一した。
既存copyrightと過去のMIT許諾全文を保持した。第三者原本、package metadata、historyと過去の
hash付きevidenceは改変していない。DebianやLinux全体をBSDへ変更したという意味ではない。
判断はADR-0088、範囲は各repoのLICENSING.md、公開手順はworkspaceのdev/PUBLISHING.ja.mdを参照。
標準文面は[BSD 3-Clause](https://opensource.org/license/bsd-3-clause)、第三者の扱いは
[Debianのlicense情報](https://www.debian.org/legal/licenses/)も参照する。

## 変更と見直し

895個の正本fileのSPDX表記を機械的に変更した。generator内の出力表記も含む。
共有vendorを直接編集せず、既存工具でsource・profile・公開試験用署名fixture・CI・inventoryを再生成した。
正規工具がlicense noticeも同期するように追加し、lineageには現在の後継を記録した。
台帳や署名を無効化して変更を通したものではなく、本番鍵・本番policyは生成していない。

code-change-review.jsonで実行コードの差分を分類した。正本の860 fileはSPDX以外のbytesが同一、
三つは生成されたhash定数/期待hash、三つはlicense検査のmake接続とnotice同期工具の変更である。
895と860は数える対象が異なる。前者には設定file等も含む。別に新しいdev/check-licenses.pyと
license文面・説明を追加した。意図しないアルゴリズム変更、保護された履歴の変更はこの差分にない。

root準備のpolicy、socket peer、実CAS予約FDの受渡し、workerの制限、永続bank、復旧結果と
公開/bootの分離も静的に確認した。packageのcopyrightには既存の二つの権利者表記を保持した。
これはrepo全体の独立した監査や、欠陥がないという証明ではない。

## 実検証

固定SDKで新規source exportから全コンポーネントを実compile/linkし、標準124工程が成功した。
登録された75 Ada mainすべてが成功。Pythonは597試験を発見し、環境境界を明記した11 skipを含む。
標準実行はstandard/engineering-nje3x1w5/で、source subjectは
`e8835db7da6440f4ce5a86cc72cc00215860c727fac76fb5bbaabd3c576e9c8a`。

標準実行後の製品source差分はpackage copyrightへの既存権利者一行の補足だけである。
全compile/testコードは同じbytesで、最終license/traceability/link検査も成功した。
rootのAGENTS/STATUSの進捗更新はbuild入力から分けて記録する。
数学的アルゴリズムの変更はないが、profileやraw source hashが変わるため、過去の形式証明を
新しいsubjectの成功へ読み替えない。今回は新たな全体形式証明・旧カオスcampaignを行っていない。

初回二回は、私有exportに参照される過去の証跡文書を含め忘れ、source検査で停止した。
compile開始前の失敗である。実文書をそのまま補い、リンク検査で確認してから最終実行を開始した。
検査を省略したり、空の代替fileを作ったりしていない。export-correction.jsonと初回ログも保持する。

最終BSD packageの18入力は現行repoと同一。使い捨てDebian 13 VMで別directoryから主DEBと
dbgsymをbuildし、双方の実バイト列一致を確認した。主DEBのSHA-256は
`538dda41e2357d74d9706626f9dc6ec721e82846fd54ec348a542bf8a62f54b9`。
旧MIT開発DEBとは別のbytesであり、公開済みassetを上書きしていない。どちらも未公開の開発候補である。

実unit・専用account・native driverから元人工DEBを展開し、207 assertionが成功した。
再起動後の履歴、bank lock/CAS lock/設定の独立した欠損拒否、元inodeの明示復元後の履歴も成功。
driverは新規にcompileした結果が以前の受入binaryと同一だった。全binaryが変わるとは仮定しない。
ELF workerも以前と同じhashである。実build依存版はvm/の.buildinfoに保存した。

外側3 GiB/swap0/CPU1/pids128、VM2 GiB/1 vCPUを維持し、重いjobは逐次実行した。
全jobとVMは終了済み。VM disk・秘密鍵・runtime library・DEBはGitへ格納しない。
私有labはbsd-license-transition-01。主DEBはそのvm-bsd-service-01/に保持する。

## 公開と残る工程

必要時のminto-dane名義でのrepository作成とReleases利用は許可され、ghの同名認証を確認した。
今回はremote作成・push・release公開を行っていない。公開するGit履歴と成果物の点検、実連絡先、
署名と対応sourceを含む配布条件は公開時に確定する。source公開を製品の本番認定と混同しない。
製品installer/controller、独立認可/供給provider、容量予約、物理再検証/回収、全DEB効果、
起動切替、完全置換ISO、全言語翻訳は引き続き未完である。
