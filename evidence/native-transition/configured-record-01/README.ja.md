# 設定済みrootの保存参照読込 — 2026-09-11 UTC

対象source subject: `78bfa9040cd90d8374765d1fc20dd46224aad6792e60c11935e099537e45baa0`。
判断ADR-0106、REQ-144、HAZ-130、FAULT-143。実行結果は`report.json`。

Pkg_Configured_Root_Record.Loadを追加し、既存のlive Verifyの先行検査に接続した。
保存物のhash・元/選択binding・長さ/順序/サイズ・宣言閉包の和集合を読み戻す。
CASへ書かず、欠損を再生成しない。生存するproposal、認証済み同意、実行権限は復元しない。
既存Verifyはその後もlive配置・所有権・全選択とBuild結果の完全一致を要求する。

## 実行

固定Debian 13開発imageは`dev-image.id`。外側の`dev/run-limited.sh`で3 GiB、swap0、
CPU1コア分、pids128。各ログ先頭にkernel制限の読戻しがある。全工程を逐次実行した。

- `test-02.log`: 対象mainを`gprbuild -f -j1`で強制compileし、既存190 assertionが成功。
- `oracle-01.log` / `root-oracle-01/report.json`: 今回生成した6 rootの元span・全選択・閉包集合を独立照合。
- `oracle-02.log` / `record-oracle-02/`: 最終35ケース。各ケースで別の普通UIDプロセスを起動し、
  CASを再openする。live proposalを作らず、全binding・入力順choice・配置順設定・保持memberを読み戻す。
  6 rootの返却全fieldをPythonの独立wire読取と比較した。
- 不整合な形式/長さ、scope、件数/位置/サイズ、保持集合の過不足/非整列/重複、選択閉包bindingを拒否。
  root/manifest/retention/base/proposal/decision/choice closure/prefix/content/catalogの10個別欠落も拒否した。
  各読込前後のCAS object集合・内容が一致し、欠落はreader終了後も未修復のまま残った。
- 旧proposalのboottime期限を1にした保存参照も履歴として読めた。これは新しいproposalではない。
  native helperは有限期限とgetter範囲外/失敗時の出力消去も検査する。
- `compile-inputs.json`の399入力、`fixture-inputs.json`の26既存入力、`executed-tools.json`の6 Python工具を
  現行ソースと実行コピーでbyte照合した。fixtureは変更しておらず再生成は繰り返していない。
- `source-checks.json`と各ログ: 構造/link/lint、統合静的監査、license、生成CIの一致が成功。
  source subjectは検査前後で一致した。保存記録oracleを標準component CIと統合runnerへ接続した。

## 途中経過

`test-01.log`はByte演算子の可視性不足でcompileが停止した記録である。
`use type Byte`を追加し、最終test-02で成功した。失敗ログは残している。
`record-oracle-01/`は34ケースの最初の成功で、その後に旧期限の1ケースを追加した。
当初のPython driverは追加差分を除いて`attempt-01/`に保存した。最終の工具hashは現行35ケース版である。
同じ34ケースを独立した追加coverageとして二重計上していない。

## 適用範囲

これは保存参照整合性と従来live検証の受入である。保存loader単独では原本由来の閉包完全性、
所有権/配置/設定効果の意味、同意・期待digest/scopeの真正性や現在のroot状態を保証しない。
旧期限が読めることを失効した実行許可の復活に使わない。最大件数までの実運用負荷の認定でもない。
member列挙はNIACRC01自身を含まず、将来の保持rootは両方の記録を保持する必要がある。

世代pin/GC・認証済み復旧・実root準備/公開/boot、全DEB効果、本番provider、完全置換ISOと全言語翻訳は未完。
プロセス再起動の受入であり、VMや実機の再起動・復旧適用の認定ではない。
共有vendor/数学的入力、特権workerとfixtureは不変で、全suite/証明/旧カオス/VMは反復していない。
私有labは`/home/nia/devbox/niaos/.work/native-configured-record-01`。CAS、ELF、秘密鍵、VM diskはここに含めない。
