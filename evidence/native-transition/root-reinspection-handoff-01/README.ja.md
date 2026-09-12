# 保持rootの再検査handoff

`report.json`は実装/試験ソースと実バイナリを束縛する。`source-inputs.json`は独立した
作業directoryへexportしたコンパイル入力で、検査後も現行原本と全hashが一致した。

- `compile.log`: AdaのReinspect APIを含む実mainとC runtimeのコンパイル。
- `transport.json` / `transport.log`: 隔離root containerから非rootの実子processへ渡した
  private socketで32ケースを実行。実kernel credentials/pidfd、SCM_RIGHTS、借用FDと
  予約保持、準備/再検査のAda往復、対象不一致、準備ACKの拒否、取消・期限・再送拒否。
- `proof/`: CBMC 6.6.0-4による288 property成功とGCCの厳格な静的解析。
  対象は準備/再検査の純粋wire validatorおよびそのhelperのみ。任意byte/length/deadlineと
  NULLを扱う。192/224 byteの読取可能objectという仮定を持ち、OSモデルを導入していない。
- `typing.log`: root側ChannelとReinspectionScopeのstrict typing。
- `engineering.json` / `lint-summary.json` / `license.json`: 構造・参照・ライセンスの限定検査。

固定imageと実行上限はreportに記録する。重い処理は3 GiB/swap0/CPU1/pids128で逐次実行した。
本番の鍵や認可ruleは使っていない。root identityと元期限は通信fixtureの固定値であり、
有効な物理rootを保持した証拠ではない。実controllerのObserve、独立観測、現在認可/供給/同意を
一貫したsupervisorへ接続する作業は未完。全C/FFI/OSの形式証明・規格適合もこの結果では証明しない。
実DEB/ISOを再構築しておらず、配布済みpackageや製品全体の受入として扱わない。
