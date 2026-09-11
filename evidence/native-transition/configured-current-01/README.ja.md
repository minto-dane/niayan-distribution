# 新しい予約での設定再観測と全root照合 — 2026-09-11 UTC

対象source subject: `972bb968e5f4def48ad3496808add2ede374315cc2e6c1266fc82ab0661d9b19`。
判断ADR-0107、REQ-145、HAZ-131、FAULT-144。集計は`report.json`。

世代処理がCASを開き直す境界へ接続するため、現在のsourceを再観測する内部APIを追加した。
Pkg_Conffile_Choice.Reobserveは旧proposalを復活させず、新しい予約で原本・宣言・現在のinode/属性/内容・
退避先を通常Prepare/Resolveから観測し直す。保存choiceの全fieldとsource閉包を比較する。
観測期限とその新record参照だけを区別し、保存されたbyteとhashは更新しない。

Pkg_Configured_Root.Verify_Currentは保存閉包を先に検査し、独立した期待bindingと全再観測choiceを
通常Buildへ接続する。元所有権・配置・prefix/content・全tarを照合し、最後に新choiceをlive再確認する。
返却するのは一致を確認した保存archiveである。未pinの新規観測/派生CAS objectは作り得る。

## 検証

固定Debian 13開発imageは`dev-image.id`。全工程を3 GiB・swap0・CPU1コア分・pids128で逐次実行した。
各起動ログ先頭にkernel制限の読戻しがある。実rootやhostでの設定適用は行っていない。

- `test-02.log` / `choice-test-01.log`: 強制compileと設定選択297 assertionが成功。
  旧270 assertionを維持し、local/vendor、特殊permission、remove/purge、宣言削除、宣言消失と初回導入の
  9経路を別期限で再観測した。新proposal/decision/closureの別identityとlive recheckを確認した。
- `root-test-01.log`: 全root192 assertion。既存190に、独立期待contextと保存root欠損の新API拒否を追加。
- `current-oracle-01/`: 計13ケース。別の普通UIDプロセスでCAS/rootを開き直し、現在のempty設定を受理、
  過去5種類の観測をStaleで拒否した。ownership binding、設定prefix、tar byteを変えた3ケースは、
  保存参照Loadでは受理されるがVerify_CurrentではConflictとなった。旧期限1の選択も現在の条件が
  一致するときに再観測できた。過去の全CAS memberとmanifest/closureは元hashのままである。
- `root-oracle-01/report.json`: 今回の6 rootの原本span・全選択・exact閉包を独立Pythonで照合。
- `record-oracle-01/`: 保存参照35ケースの回帰も成功。構造検査と現在の意味検査を混同していない。
- `compile-inputs.json`: 399入力、`fixture-inputs.json`: 26不変fixture、`executed-tools.json`: 7 Python工具が
  現行ソースと実行コピーで一致。current oracleの最終版は、元fixture driver終了より前に配置済みだった。
- `source-checks.json`と各ログ: 構造/link/lint、統合静的監査、license、生成CIの一致が成功。
  source subjectは検査前後で一致した。current oracleを標準component CIと統合runnerへ接続した。

current oracleは元fixture driverと**同じmount namespace**で実行する必要がある。
標準CIと`test-02.sh`はこの順序を維持する。別namespaceやOS再起動のmount identityを無視する試験ではない。

## 途中経過と最終入力

`test-01.log`はテストhelperのFD型演算の可視性でcompileが止まった記録である。
宣言の順序を修正し、test-02で両mainと全対象試験が成功した。
その後、Pkg_Configured_Root_RecordのAPIコメント1行を新APIに合わせた。
`compile-03.log`で対象mainを強制compileし、実行済みroot driverとのbyte一致を確認した。
`binary-equivalence.json`に比較を記録し、実装不変の試験は反復していない。
旧コメント版のspecは`before-doc-comment/`に保存した。ELF自体は含めない。

最終root driver SHA256: `44df0a7061e8c92dc381e4fb5f450a074f9e1dcf1e3b720c5dc7437a89a062a0`。

## 適用範囲と残る条件

観測の新しい期限は、同意・失効・新規要求の真正性・復旧実行許可を更新しない。
callerがroot FD、期待scope、保存選択と使用の認可を独立して検証し、使用境界で再確認する必要がある。
今回の受入は同じmount namespaceの新プロセスでの再観測である。mount/inode identityの変化は拒否する。
boot後のidentity移行、設定適用後のaccepted状態の復旧、新規／記録済み認可の本番providerは未完。

世代形式・pin、実root準備・公開/bootへこのAPIを接続する作業、世代GC、全DEB効果、完全置換ISOと
全言語翻訳も未完である。全root照合の成功を公開・起動切替・本番認定としない。
共有vendor/数学的入力、特権workerとfixtureは不変で、全suite/証明/旧カオス/VMは反復していない。
私有labは`/home/nia/devbox/niaos/.work/native-configured-current-01`。CAS、ELF、秘密鍵、VM diskは含めない。
