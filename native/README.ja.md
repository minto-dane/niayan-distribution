# Niaパッケージ管理への完全置換

[設定ファイル宣言と三者比較](conffiles.ja.md)で、元DEBの設定と利用者の編集/削除を区別する。
全属性・効果・実rootへの反映と公開認可への接続は引き続き必要である。

[現在site trustによる供給計画](supply-planner.ja.md)は保持原本を実observerへ渡し、
同じCAS予約で供給map/保持policyへ接続する。公開controllerと全managed認可は別の未完工程である。

[製品判断](../docs/decisions/0002-native-package-authority.ja.md)に従うTrixie置換工程。
[隔離rootの実展開worker](root-extraction.ja.md)を実装した。認可済みサービス・永続bankとbootへの接続は未完。
[専用bankの書込排他](root-freeze.ja.md)を内部controller部品として実装した。[専用bankの明示配備](bank-device.ja.md)を追加した。完全置換ISOのpartition recipeとcontroller接続は未完。
[受理済み世代のnative catalog観測](current-catalog.ja.md)を同じ排他区間へ接続した。
[確定済み世代からの更新計画](current-transition.ja.md)は同じ予約で候補の保持と通常更新を検査する。
[公開計画へ束縛したnative検査記録](publication-intent.ja.md)を保存し、公開時の必須再検査へ接続する。
[正規catalogのCAS保存と再構築](catalog-store.ja.md)を追加した。
[既存世代の変更集合と保護対象](transition-plan.ja.md)の読取SDKを追加した。
[機能の管理主体](ownership.ja.md)にNiaが引き受ける役割と独立した基盤を整理した。
[DEBトリガーの解析と発火先](deb-triggers.ja.md)を元DEB読取器と候補catalogへ追加した。
現段階のPython工具は移行対象の実データ検査であり、インストーラーや特権writerではない。
[元DEB読取SDK](deb-container.ja.md)でar envelopeと圧縮メンバーを既存CASへ束縛する。
[圧縮制御ファイルの読取](deb-control.ja.md)も同じCASへ接続した。
[制御項目と識別情報](deb-metadata.ja.md)まで元DEBから検査する経路を追加した。
関係項目を含む全意味、全効果と適用接続は別の未完条件である。
pkgcoreには[非公開世代の組立てSDK](generation-stage.ja.md)を追加した。
既存CAS/WALで分割適用と全体検査を行い、[公開SDK](generation-publication.ja.md)で
root/catalogを単一の論理世代として確定する。実mount/bootと稼働管理器への接続は未完。

公開管理コマンドは[最新判断](../docs/decisions/0003-management-interface.ja.md)に従う。
[コマンド解析](commands.ja.md)と[更新緊急度・修正告知の識別](update-metadata.ja.md)を追加した。
[媒体索引と一覧](media.ja.md)をinutoc・installp・geninstallへ接続した。
[緊急修正成果物](interim-package.ja.md)の決定的な作成と読取をepkg/emgrへ接続した。
[共通の供給認証](repository.ja.md)と`emgr_download_ifix`のHTTPS取得も実装した。
[Debian 13原本とTUF供給policyの認証](archive-supply.ja.md)で、明示したInReleaseから元DEB/controlを照合する。
[新規原本の供給記録集合](supply-map.ja.md)は候補−基準の正確な差集合を照合し、保持検査と新規認証を分ける。
[署名付き供給記録](archive-receipt.ja.md)は実認証後に発行し、native SDKで独立authorityとCAS原本を
再照合する。本番observer/key配備と、公開計画の変更集合・保持閉包への接続は未完である。
署名済み成果物と参照の認証は、稼働システムへの適用許可とは別に検査する。
[多言語表示](localization.ja.md)は共通のgettext層を使用し、操作要求と表示言語を分離する。
外部ソフトウェアの管理コマンドは包まず、Niaの管理操作の入口だけを統一する。
緊急修正は通常パッケージと同じcatalogへ接続する設計で、適用器は未実装である。

```sh
python3 native/audit_transition.py \
  --status /offline-metadata/var/lib/dpkg/status \
  --info /offline-metadata/var/lib/dpkg/info \
  --output /new-output/transition.json
make native-check
```

停止したビルドroot又は完成ISOから抽出したメタデータを使う。
対象を稼働中のdpkg DBへ向けない。工具はstatusの再読と個々のファイルの安定性を
検査するが、実システムのDPKGロックを取得するsnapshot機構ではない。
出力にはstatus/control全件のSHA-256、版と関係の検査、除外対象、効果ファイル、
コマンド出現箇所が含まれる。既存レポートを上書きしない。

除外リストは既知のwriterと管理器依存群を探す開始点であり、全実行経路の
不存在証明ではない。PackageKitの存在自体で二重書込が起きたとは断定しない。
元のDEBを読み取る`tools/deb_archive.py`、認証する`tools/debian_archive_auth.py`、
最終集合を再検査する`tools/debian_semantics.py`と接続する前の観測である。

| 工程 | 状態 | 完了条件 |
| --- | --- | --- |
| 旧実ISOの移行対象検査 | 実行済み | 全2,239個のstatusと8,959個のcontrolファイルをhash照合 |
| 元DEBからの効果変換 | 未完 | 全採用パッケージと暗黙triggerについて版付き契約を実装 |
| Native phase・解決器接続 | 未完 | 既存の独立検査と元形式を同じ予約へ束縛 |
| full-root/catalogの確定 | 未完 | 既存CAS/WALと原子的公開・実障害復旧を接続 |
| 唯一の更新主体 | 未完 | 自動更新・GUI・CLIをNiaへ接続し別writerを除去 |
| 新ISOと更新・復旧受入 | 未完 | 実導入、更新、電源断、rollback、署名失効、操作性 |

上の未完条件を単純な真偽値で埋める実装は作らない。SPARKの局所証明は、
未接続の副作用や稼働OSの完全性を証明するものではない。

容量にも実装上の境界がある。`Pkg_File_Plan.Max_Changes`は1,024、
`Resolver_Model.Max_Items`は4,096、`Max_Claims`は16,384である。
全rootの所有権を既存の配列へそのまま押し込んだり、上限を無制限に増やしてはならない。
更新の途中を別々のcommitとして公開する分割はトランザクションを弱める。
inactive generationの組立てを有界な作業へ分け、全入力と所有権をhashへ束縛し、
最後のroot/catalog公開を一つの復旧可能なcommitにする接続が必要である。
現在の工具は`.list`のパス数も記録するが、これは実ファイル属性や差分変更数の検査ではない。

原本binary関係項目のnative読取は[deb-relations.ja.md](deb-relations.ja.md)を参照。

原本dataメンバーのstream保存は[deb-data-stream.ja.md](deb-data-stream.ja.md)を参照。

採用tar profileの内容・属性・リンク保持は[deb-payload.ja.md](deb-payload.ja.md)を参照。
世代形式・実行器の拡張と稼働rootへの接続は未完である。

[全原本のclaim索引](payload-index.ja.md)で属性と所有権主張を保持するnative層を追加した。
共有pathの全ownerと属性差、原本内hardlink、暗黙parentと非directory祖先を保持する。
索引化は実効所有者の選択・catalog認可・世代実行の代用にはならない。

[世代image候補の属性受入](generation-image.ja.md)で上流工具へのtar直接入力を調べた。
固定版の当該経路は属性欠落・時刻不一致のため未採用。原本の属性要件は維持する。

選択した原本・control期待hash・payload索引を完全照合するprivate候補は
[selected-catalog.ja.md](selected-catalog.ja.md)を参照。稼働catalog/認可と全関係の意味検査は未完。

候補の必須依存・競合・architectureと共存版の検査は
[final-set.ja.md](final-set.ja.md)を参照。実行順序・稼働認可と実効所有権は別工程。

[catalog由来のCAS保持閉包](catalog-retention.ja.md)で、原本・control内容・payloadと属性の
正確な一覧を既存pinへ束縛する。全世代・効果・認証・復旧rootの保持とGC削除認可は別工程。

[版付き世代保持](generation-retention.ja.md)は既存世代pinからこの一覧を参照し、
組立て・公開・現世代native観測で再生成前の欠落検査を必須とする。

供給認証を実公開計画へ結ぶNIAGEN04と新規admission/記録済み復旧の境界は[公開供給ポリシー](publication-supply.ja.md)を参照。
