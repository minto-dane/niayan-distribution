# 世代公開SDKの検証

対象source subjectは
`16a43c7b1adc304efc51f665283e4de70bf674c915a887556ada5b69262b3253`。
対象と結果の正本は[report.json](report.json)、全入力は[inputs.json](inputs.json)。

既存buildを含まない独立したpkgcoreコピーで、固定Debian開発コンテナの
`make compile-all build test`が終了値0となった。全ソースのコンパイルと
4アプリのリンク、全14 Ada mainが成功した。stageは1,180、公開は333 assertions。
試験用の準備・署名作成を含む検査数であり、製品の受入項目数ではない。

異なる長さの作業パス、入力mtime、タイムゾーンで二度目の新規ビルドも実行した。
4アプリと14試験の18実行ファイルのSHA-256がすべて一致した。
[再現性の比較](reproducibility.json)。両コピーと現行checkoutの343入力hashも一致する。
同じ固定コンパイラ・CPU構成での比較であり、異なる工具版のバイト一致は主張しない。

公開の試験は人工の二世代と実CAS/WAL・全Managed guardを使う。
構成証明には公開の試験専用seedから作る二役の実署名を使用する。
実DEBの副作用、物理barrier、独立trust floorの認定ではない。
認可拒否、期限切れbarrier、破損署名、構成sequence不足、native coverage不足、
trust floor不足、native照合拒否、最終再観測拒否を検査した。
公開中のstage/root/publication予約、commit拒否後の再開、確定前後の三つの永続窓、
応答喪失、別receipt・root/catalog/stageの拒否、候補ファイルの混同、
欠落descriptor/lock/journalと部分journalの保持も確認した。
人工の永続prefixは実電源断試験の証跡ではない。

同じ独立ビルドをrootの使い捨てコンテナへread-onlyで渡し、stageの4入口と
公開の3入口を有効な人工入力で拒否することを確認した。終了値0。
準備・形式検査を含むstage 1,100、公開34 assertions。
全コンテナはネットワーク無効で、外側のscopeでメモリ3 GiB、swap 0、CPU 1コア分、
128プロセスのkernel制限を読み戻した。重い実行は同時に起動していない。

開発Distroboxでのソース統合検査24工程も終了値0となり、前後のsubjectが一致した。
固定コンテナのAda実行とは別の検査として記録した。
全7コンポーネントの既存proof入力と完了済み実行の入力集合・hashを照合し、
不変を確認した。同じ証明は再実行していない。新runtimeは形式証明の対象外。
最小stage項目数とjournal復号の添字を修正する前の試験失敗を含む途中ログは
`attempts/`に保持した。

実mount/boot切替、稼働catalog/緊急修正holds、本番認可・独立trust floor、
全DEB意味・特権metadata、容量・同期・実電源断とrescue、完全置換の新ISO、
全言語翻訳とTUI/GUI、GitHubでの公開運用は未完である。
