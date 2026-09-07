# Nia OS: 完成条件と実装境界

対象は新規Nia OSで、供給元の管理DBを継承する方式ではない。実装・接続とターゲット検証の範囲を区別する。

| 領域 | この版 | 次に満たす具体条件 |
|---|---|---|
| Supply | 署名chain/DEB/source/receiptの非特権検査 | real Forky corpus, trusted time/key lifecycle,独立receipt実供給 |
| Semantics | Ada comparator/capability unit, Python final-set checker | 元metadataから全phase/effectsを独立にlowerしproof/runtimeで検査 |
| Installation | 読取catalog candidate/既存file engine SDK | 新規root assembler、catalogとfile WALの単一commit、rollback復旧 |
| Native scripts | 実行しない・全membersを保持 | 採用closure全体のreviewed replacement contracts。特権任意shellを追加しない |
| Config | 既存汎用schemaとnative SDK | 採用ソフトごとのinclude/env/generated/runtime observer、証拠issuer |
| Boot | LUKS2/XFS/UKIの構成仕様 | 実装disk identity、key enrollment、署名通常/rescue boot、rollback拒否と電源断試験 |
| MAC | AppArmor scoped方針 | カーネル/実profiles/observer接続。旧SELinux checkerをNia適格性に流用しない |
| HA/data | 既存state/control SDK | 遠隔認証transport、controller HA、実fencing、DB移行/復元、独立trust anchor |
| Long term | bounded journal/retention SDK | 移行可能なログcheckpoint/GC、independent floor、一貫したバックアップ復元 |
| Proof | SPARK sourceと入口 | compile/実行/flow/proof、TCBとモデル-実I/O対応のレビュー |
| Release | 読取出荷条件validator | 原本source/license保持、再現済first-party binaries、イメージ構築/署名/導入/認定 |

対象は一つのNia OS。GPU/CUDA/Steamは個別のapplication qualificationであり、対象OS名が変わっただけで上流vendor認定は引き継がない。DEBだからrootメタデータが欠ける、とも、tar属性があるから全副作用が分かる、ともしない。

この版を完成したbootable distroとして部署へ配備しない。次の実装順はroot bootstrap+phase/effect closure→exact catalog/WAL→実boot+MACobserver→単一node復旧→実HA/backend→反復qualification。履歴を削除することで未完を消さない。

XFSの実機受入、native health monitorへの単一接続、署名collector、修復stateの永続runtime接続、current-source xfsprogs供給、rescueのfeature互換性は別に完了させる。検査工具の成功でこれらを完了扱いにしない。

接続と試験の受入条件は[本番接続表](../../assurance/docs/engineering/specs/production-closure.ja.md)、変更実行の責任は[実行境界](../../assurance/docs/engineering/specs/execution-safety.ja.md)を参照する。
