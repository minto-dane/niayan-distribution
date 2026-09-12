# 非同期native管理者認証: 0.11.0 checkpoint

`report.json`は実ソース・対応ソース・DEBと観測範囲を束縛する。最終controllerの全source exportを
現行原本とDebian source tarへ照合し、実DEBのoperator_guard.pyも一致した。
pkgcoreの新規main/GPR/配布manifestは対応ソースと一致し、最終VMは既存の同一pkgcore DEBを使用した。

- `vm-final/result.json` / `guest.log`: 最終DEBの実polkit 11ケース。
  正常、既定拒否、誤plan、rule変更、authority再起動、取消/peer終了、helper SIGSTOP、
  最初の返答の滞留、重複要求、誤番号。失敗後の再利用拒否と子終了/借用FD保持も確認した。
- `typing.log` / `unit.log`: strict typingと3件の有限制御/FD解放/非root拒否検査。
  有限探索は実advance関数と独立した要求/観測履歴を使い、深さによる省略を行わない。
  全Python/Ada/FFIやOS効果の形式証明ではない。
- `vm/`: 最初の実package build。試験harnessの不要なpolkit再起動がstart-limit-hitになった。
- `vm-resume/`: 同じ導入済み成果物を再利用し、再起動を必要な境界だけに減らした10ケースが成功。
  guest.logには前bootのstart-limit-hitも保持する。製品runtimeを変更してこの試験エラーを回避していない。
- その後の設計レビューで初回返答にも1000 msの鮮度上限を追加した。最終controllerだけを再buildし、
  最終11ケースを別の専用VMで受入した。予備controllerを現行版の受入として使わない。

固定image、上限3 GiB/swap0/CPU1/pids128とVM 2 GiB/1 CPU、source/package hashをreportへ記録した。
重い処理は逐次。共有builderは読み取り専用で、試験は所有overlayに限った。
本番認証dialog、正確な計画同意、native世代admission、実効果遮断を含む全supervisorの受入は未完。
fixture ruleは各VM試験の終了時に削除した。本番ruleや保存grantを配布していない。
不変C/SPARKの全証明や全体suiteを反復せず、この版の独立再現buildも実施していない。
