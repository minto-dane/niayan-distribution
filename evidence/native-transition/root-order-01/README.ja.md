# rootの親先行順・旧形式検証・実展開

対象source subject: `cbc8eb5c0fa7511cb5a17e7f593cb27f5d5c363e683d3203b174d621ca94c56e`。
判断ADR-0103、要求REQ-141。`report.json`に対象と限界を記録する。

新しいNIAROOT2はrootを最初に、directoryをcanonical raw path順に出力する。
旧NIAROOT1の保持byteはVerify/Verify_Targetで照合できる。物理準備側へ接続するVerify_Ownershipでは、
旧順もroot/親先行を満たす必要がある。過去recordを暗黙に変更しない。

- `test-03.log`の強制compile入力で、別の新規caseを使った`test-04.log` / `native-04.log`が最終成功。
  root archive 831 assertion。8通りのdirectory採用元、適切な旧形式の受理と不適切な旧順の拒否を含む。
- `archive-oracle-04.json`: 既存13 pathの全原本span、属性、hardlink順とNIAGEN05 stageの照合。
- `export-04/report.json`: 二原本からの8通りの全選択span・親/リンク順・旧byteの独立Python照合。
- `vm-order-01/result.json`: 8通りの生成tarが同一であることを照合したうえで、1個の異なるtarを実展開。
  11 entryの数値属性、内容、mtime=-1 ns、hardlink chainを独立Pythonで確認した。
- `regression-01.log`: 設定配置・世代公開の2 mainを強制compile。設定配置136 assertion、公開variant142 assertion。
  `publication-01/oracle.json`は10 pathの元span、実stageと論理accepted状態を独立に照合する。
- `fixtures.log`: root-archive/root-preparationの各5 DEBとmanifestが固定環境でも一致する。
- `source-checks.json`: 同一subjectで構造、syntax/local link、統合構造、license、生成CIが成功した。

`compile-inputs.json`の390入力、`fixture-inputs.json`の37入力、`executed-tools.json`の6工具を
現在のsourceと実行workspace/VMへ渡したruntime内容で照合した。標準component CIと統合runnerへも
order oracleを接続した。新しいAda mainは追加せず既存のroot driverから新しいhelperを実行する。

`test-01.log`はCAS directoryのprivate権限不足、`test-02.log`はdirectory headerの末尾slash期待値の誤り、
`test-03.log`の実行段階は以前のcaseと同じ親でのstage directory名衝突によって停止した。
失敗ログを保存し、最終実行は新しいcase親directoryで行った。runtimeの検査は緩和していない。

root workerは前工程root-clocks-01で受入した同じ実行物を使い、再buildしていない。
全重処理は3 GiB/swap0/CPU1/pids128、VMは2 GiB/1CPUで逐次実行した。base diskは読取専用、
展開先は使い捨てtmpfsのnodev/nosuid/noexecである。`run-container.py`等は私有labの実行記録であり、
QEMU/SSH runtime、秘密鍵、VM disk、ELF、CASはこの証跡へ含めない。小さいtarは検証入力でありrelease rootではない。

旧記録の照合と展開可能性は別である。新しい認可planを作らずに旧世代を移行してはならない。
設定済みrootの直列化、全DEB/属性/inode効果、本番認可、保持/復旧、実boot/完全置換ISOは未完。
全言語翻訳も未完であり、ディストリビューション全体の本番認定や公開releaseは行っていない。
数学的入力/共有vendorは不変で、全suite/証明/旧カオスは反復していない。
