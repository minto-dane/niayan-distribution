# 保存属性の設定entry変換と実効ACL mode

ADR-0104 / REQ-142 / HAZ-128 / FAULT-141。対象sourceはreport.json。
完成した全rootや本番認可ではなく、保存属性からの通常設定entry生成と、既存読取・展開照合の修正である。

## 実装と検証

NIACOBS1/元DEBを再観測し、数値assertionと内容を照合してheader prefixをCASへ保存する。
ローカル保持、backup、vendor採用、ローカル権限を継ぐvendor採用の4経路を検査した。
原本ACLを保ち、modeのgroup classにはmaskを用いる。上流archive entryのmode自体は変更しない。
未知属性、範囲外ACL identity、未解決link、期限切れや不整合は出力を消して拒否する。

最終Ada実行はtest-04.log（設定観測/変換141、既存payload814）、tarはtest-03.log（83）。
root-regression/native.log（831）、configuration-regression/native.log（136）も対象ソースで再compileした。
export-04は独立NIACOBS1/DEB読取とnative payload 4回各26 assertion。
export-ciは同じ検査をCIのdriver起動経路で実行した結果であり、別の機能caseとは数えない。

vm-package-01で0.2.2の2 build directoryの主DEB/dbgsymが一致し、導入後に既存root worker 7 caseが成功。
vm-entry-03では同じ導入済みbinaryで隔離ext4上の4設定entryを展開し、内容・数値権限・ACL/xattr・flags・
mtime/atimeを独立した期待値と照合した。worker hashは双方のworker.logで一致する。
ctime/birthtimeは履歴であり任意復元を主張しない。

## 途中失敗

test-01はAda演算子の可視性、test-02はfixture directoryの相対pathを検出した。
最初の独立観測decoderのtag幅の誤りを修正した（初回出力は会話記録のみ）。
roundtrip.logとdiagnosticsのnative記録で、group owner/mask混同によるmode差を検出し、SDKとworkerを修正した。
vm-package-01は既存7 case終了後のmkfs工具PATHで停止した。
vm-entry-02は再起動で消えるguest /tmpを再利用できず停止した。
vm-entry-03は必要な小入力を再展開して同じ導入済みpackageを使用した。buildや既存7 caseを重複実行していない。
失敗ログを成功ログへ置換していない。

## 境界

3 GiB/swap0/CPU1/pids128、VM 2 GiB/1CPU。ホスト実disk・稼働rootは操作せず、VMの専用32 MiB fileだけをformatした。
VM disk、秘密鍵、CAS全体、ELFを証跡へ含めない。compile/package/fixture/toolの入力hashを現行sourceと照合した。
全suite・形式証明・過去カオスは反復していない。

全root stream/保持、live選択再検証・production provider、隠れた属性と全inode効果、旧計画移行・復旧、
実root/boot、完全置換ISO、全言語翻訳とGitHub公開は未完である。
