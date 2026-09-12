# root worker実行中の取消: 0.9.0 checkpoint

`report.json`は実ソース・対応ソース・DEBのhash、工具、資源上限、検査範囲を記録する。
単一buildの同じDEBを二つの新規専用VMへ導入した。独立再現buildやOS全体の出荷認定ではない。

- `unit.log` / `typing.log`: 実プロセスの通常/非零終了、容量、期限、起動前取消、
  停止中のworker/子孫に対する接続断・packet取消・依頼元死亡、有限状態遷移の全探索。
- `vm/result.json`: 実native workerをSIGSTOPし接続断。pidfdによる終了、RO化、
  attempt保持、再要求拒否。約0.076秒はこの実行の観測値であり保証上限ではない。
- `vm-normal/result.json`: 同じDEBのprepare/freeze/物理verify/observe/closeと既存の入力拒否。
- `source-inputs.json`: Debian source exportの全入力。DSC/source tarと実DEBのmoduleを元sourceと照合。
- `guest*.sh` / `vm*.py` / `run-container.py`: 実行手順。専用overlay・64 MiB bankだけを変更。
  3 GiB/swap0/CPU1/pids128、VMは2 GiB/1 CPU。共有baseは読み取り専用。

最初のVM起動は実行identityによるKVM権限拒否。既存非root runnerで解決し、host deviceの
権限は変更していない。初回の3取消試験は検査後の後片付けで既に終了したpidfdへのsignalが
ESRCHになった。試験のcleanupを修正した経緯はreport.jsonに保持する。

有限制御検査の保証は起動/停止/回収の順序と再開禁止に限る。kernel I/O、Python全体、
第三者root writer排除、認可/同意や全DEB効果・boot/復旧の完成を主張しない。
正常経路と取消経路の受入後に同じ全体suiteやC/SPARK証明を再実行していない。
