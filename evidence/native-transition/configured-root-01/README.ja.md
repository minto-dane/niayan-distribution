# 設定済みrootの生成と保持

ADR-0105 / REQ-143 / HAZ-129 / FAULT-142。対象sourceはreport.json。
設定配置から原本spanと属性付き設定entryを完全なtarへ流し、同じCASへ保存する新しい内部SDKの検証である。
NIACRT01は元binding・全選択・出力を記録し、NIACRC01はcatalog/choice閉包と全生成物のexactな和集合を保持する。

## 実行

対象mainを強制compileしたtest-02.logで190 assertionが成功。
初回test-01の174 assertion成功後、保存root欠落・明示再構築、容量、live変更、空fileと大きな原本本文のケースを追加した。
失敗した検査を弱めた経緯はない。

独立Pythonで6 rootの原本span、内容、削除/退避、数値属性/時刻、選択binding、prefix/content、
保持集合の過不足を照合した。export-02/report.jsonは最初の独立照合、export-ci/report.jsonは固定環境の同じCI工具の結果。
6 caseを二重の機能coverageとは数えない。既存24 DEBはbyte不変、新しいlayout-streamだけを追加した。
25 DEBとmanifestは固定環境で再生成照合に成功した。65,537 byteの元本文でstream境界とpaddingを確認した。

vm-configured-01で6 root（計26 entry）を使い捨てext4へ展開した。
ローカル保持、vendor採用、普通のhardlink chain、削除維持、復元、空fileを確認し、
最終namespace、元/設定内容、mode/UID/GID/mtimeと明示atime、設定xattr/flagsを照合した。
この統合fixtureは拡張ACLなし。複雑なACL/raw xattrの前工程を今回再実行したとは主張しない。
特権worker sourceは不変で、今回の固定環境buildも前工程の私有buildとbyte一致した。
上流sourceを変更せず、同じworkerへ新しく生成した全rootを渡した。

## 証跡と境界

395 compile入力、26 fixture入力、12 Python/worker入力を現行sourceと照合した。
標準component CIと統合runnerへ独立oracleを接続し、構造/link/lint/license・CI生成検査が成功した。
3 GiB/swap0/CPU1/pids128、VM 2 GiB/1CPU。VM disk、CAS全体、秘密鍵、ELFをこの証跡へ含めない。
全suite/形式証明/過去カオスは反復していない。共有vendorと数学的入力も不変。

生成はlive proposalを必要とする。新形式の世代/pin/GC/実root準備・公開/boot接続、durable復旧loader、
全過去設定/隠れた属性/inode/DEB効果、本番provider/認証UI、完全置換ISO、全言語翻訳は未完。
CAS記録の存在やfixture展開を本番認可・起動切替・完全なディストリビューションの完成と扱わない。
