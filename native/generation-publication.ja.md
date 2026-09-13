# 世代とcatalogの単一確定

`pkgcore/runtime/pkg_generation_publisher.*`は検査済みのstageとcatalogを
一つのdescriptorへ束縛して確定する非特権内部SDKである。
[設計判断](../../assurance/docs/engineering/adr/ADR-0056.ja.md)を参照。
実mount/boot切替と変更コマンドはまだ接続していない。
確定状態の照会は共通のPkg_Generation_Readerへ分離し、lslppの一覧と更新準備へ接続した。
詳細は[確定済みカタログ](accepted-catalog.ja.md)。

## 呼出しと予約

1. [stage組立て](generation-stage.ja.md)を完了し、bankの`<stage-id hex>/root`と
   `<stage-id hex>/state`へ保存する。
2. 同じCASに新descriptorと公開プランを保存する。`Descriptor.Compile`は
   root/catalog、直前descriptor、世代番号と固定一項目プランを検査する。
3. 必須の本番認可・barrier・二役の構成証明・独立解決検査・native照合・最終再観測を
   接続したManaged engineと、stage認可・bootstrap認可からPublisherを生成する。
4. 空のprivate root/stateを明示的にProvisionする。既存管理状態を再初期化しない。
5. Publishへプランdigest、認証対象health receipt、有限のBOOTTIME期限を渡す。stageを全検査して予約を
   保持したまま、全Managed guardを通して既存ファイル実行器で確定する。
   [native形式の保持閉包](generation-retention.ja.md)を必須とし、全掲載objectを先に検査する。
6. Read_Currentでaccepted planが参照するdescriptorを読む。進行中はIndeterminate、
   初回確定前はStaleとなる。失敗時はdescriptorが空になる。

`generation.next`にはApplyで未確定の候補が書かれる。利用者や起動器はこれを
現行世代として読んではならない。権威はroot.stateの確定済みAccepted_Planと
そのCAS descriptorであり、rootとcatalogは同じdescriptorから取得する。
公開の世代番号とstage内部の分割番号は別である。

publication.lockはstage検査と実際の確定の間も保持する。stage側のgeneration.lockと
root.lockも保持し、検査後の協調writerによる変更を防ぐ。予約に従わない特権変更を
このSDKだけで排除できるとは主張しない。将来のGCも同じ排他規則に従う必要がある。

記録済みの要求は同じプランとreceiptで再開する。結果不明のjournalは保持し、
自動修復、health receiptの差替え、再bootstrapはしない。
Read_Currentは物理rootの全検査やboot健全性、管理認可を代替しない。

## Descriptor形式

整数はbig-endian、予約領域はzero。全長192 bytesで、余分な末尾を拒否する。

| 0起点offset | bytes | 内容 |
| --- | --- | --- |
| 0 | 8 | `NIAPUB01` |
| 8 | 16 | 公開root identity |
| 24 | 16 | stage identity |
| 40 | 32 | stage manifest SHA-256 |
| 72 | 32 | catalog SHA-256 |
| 104 | 8 | 公開世代番号（1以上） |
| 112 | 32 | 直前descriptor SHA-256（第1世代だけzero） |
| 144 | 16 | zero予約領域 |
| 160 | 32 | 先頭160 bytesのSHA-256 |

このchecksumは署名や実行許可ではない。世代間のcatalog、構成、全入力と効果の意味は
必須adapterが独立検査する。常時成功adapterを本番用には提供しない。

## 検証と製品の残条件

`run_generation_publication_tests`は人工の二世代と全Managed guardを実行し、
構成証明には試験専用の二鍵による実署名を使う。実DEB効果や物理fencingの検証ではない。
root拒否は使い捨てコンテナ内の`ci/generation-root-refusal-test.sh`へ登録する。

実mount/boot切替、稼働catalog/緊急修正holds、全DEB意味、特権metadata、本番認可、
独立trust floor、容量・同期故障・電源断とrescue、新ISOの更新・復旧受入は未完である。
