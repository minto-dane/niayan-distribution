# root統合の開発checkpoint（本番未認定）

この記録は、試験をリリース直前へ延期する利用者の追加指示**より前**の実行である。
以後はVM/挙動試験を再実行していない。当前ソース全体のPASSとして使わない。

- vm-normal: 実DEB、実polkit、非rootのnative C handoff、実ext4展開、独立root FD/記録照合、
  同じcontrollerでの再検査、終了EOFまで成功。供給/計画同意/CAS取得はfixture。
- vm-cancel: 同じDEBを再利用。実native抽出workerをSIGSTOPし、実polkit ruleを失効した。
  worker終了、全bankのRO化、元attempt保存を約0.177秒で観測した。最悪時間の保証ではない。
  **試験全体は失敗**。native childの結果待ちが失敗し、fixture peer後片付けも失敗した。
  fixture actorがforkでroot handoff端点を継承する問題を修正したが、再実行は延期している。

対象はtested-service-inputs.jsonの0.12.0 sourceとartifacts.jsonのDEBだけ。
現在ソースには、この実行後の解放エラー処理、応答回数制限、依存宣言の変更もある。
Ada Pkg_Generation_Execution、Debianイメージレシピの変更はこのVM試験に含まれない。
Ada実行器は厳格compiler設定でコンパイル済み、全経路の実行・形式検証は出荷前に必要。

採用コマンドからの本番launcher、現在供給/世代認可/正確な同意provider、全writer排他、
全DEB効果、catalog/boot切替、完全置換ISOは未完。署名鍵や無条件許可を製品へ導入していない。
VMは各2GiB/1CPU、外側3GiB/swap0/CPU1/pids128。秘密鍵・VM disk・DEB本体はGit外。
