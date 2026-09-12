# 独立供給方針の初回配備: 0.10.0 checkpoint

`report.json`は実ソース、DEB、対応ソースと適用範囲へ束縛する。
`source-inputs.json`の全29入力を現行原本、export、Debian source tarと照合し、
実DEB内のsupply_initialize.pyも原本と一致した。pkgcoreの変更mainはsource tarと一致する。

- `vm/result.json`: 最終実DEBの正常、不一致floor、期限切れ、公開3境界のSIGKILL。
  再試行の拒否、記録/状態保持、非root初期化の拒否も確認した。
- `unit.log` / `typing.log`: 6件の単体・有限制御検査とstrict typing。
  有限探索は順序/回数/終端性のみで、OS効果や全runtimeの形式証明ではない。
- `component/` / `controller/`: 実buildのDSC、buildinfo、changes。バイナリと対応ソースは
  private labに保持し、Gitにはhashと記録を置く。全OSのrelease成果物ではない。
- `guest*.sh` / `vm*.py` / `run-container.py`: 専用VMの実行手順。
  共有baseは読み取り専用。上限3 GiB/swap0/CPU1/pids128、VMは2 GiB/1 CPU。

最初のcompile imageにはdpkg-buildpackageがなく、packageは生成されなかった。
専用Debian VMでpkgcoreを標準recipeからbuildし、初期版controllerの6ケースが成功した。
その後のレビューでFD解放処理とpath上限を修正し、最終controllerを再buildした。
pkgcoreは同一DEBを再利用し、変更境界の6 VMケースだけを再実行した。
この記録のcontrollerは最終版であり、予備版を現行受入として使わない。

方針とfloorが公開された後、完了応答前に停止すると、整合した組が既に読める。
これは不確定な完了であり、rollback・未実行・自動再試行の許可ではない。
fixtureの公開鍵は専用VM試験用。本番鍵配備、供給元の署名authority、独立した非rollback
anchor、運用更新/復旧、認可/計画同意との全体接続は未完。SIGKILLは実電断ではない。
不変C/SPARKの全証明や全体suiteを反復せず、この版の独立再現buildも実施していない。
