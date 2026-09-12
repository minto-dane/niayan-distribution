# 実装保証基準の導入と限定C証明

2026-09-12 UTC。source subject: `462da7431ca1adb554a012199e26649b33bb3f3a0c785fe34590d345bbda53f6`。
規範はassurance/docs/engineering/specs/implementation-assurance.ja.md、判断はADR-0117。
この証跡は全実装の適合や航空宇宙認証を意味しない。

実runtimeのroot_handoff_wire.cと到達する純粋helperについて、CBMC 6.6.0で208条件が成功した。
入力はNULLまたは読取可能な初期化済み192byte object。内容/length/deadlineを正常値へ制限しない。
amd64 C11で正規形式との同値性、0/1結果、メモリと整数操作を検査した。
反復上限33とunwinding assertionを用い、上限2の負の対照では実際にunwinding失敗を観測した。
negative-controlは期待する失敗の確認であり、そのCBMC実行自体は成功ではない。
OS/外部libraryのモデル化はしていない。この証明を通信・認証・FD寿命の保証に広げない。

container-proof-02が現在のrunnerに対する結果。GCC14の厳格警告と-fanalyzerは
実オブジェクト生成(-c)を伴って実行し、診断なしを確認した。以前の-fsyntax-only実行を
analyzerの受入に流用していない。proof reportは全入力/工具/仮定/制限を保持する。
CBMC実行物と供給DEBのhashを固定した。工具と依存は私有labへ展開した。
root repoはengineering subjectの外なのでroot-inputs.jsonへ別途hashを保持する。

自作Cは16unit（runtime11、検証用5）。全Cの規則適合・形式検証は未完。
Ada/SPARK対象外・FFI・特権Python・UI/多言語・シェル/配布/CIも新基準の対象である。
既存のSPARK/通常試験/sanitizerを、その対象外実装まで証明した結果と数えない。

CI定義と依存固定は更新した。既存の固定development imageと展開した固定CBMCで
最終runnerを検査したが、新dev imageの全buildとremote CIは未実行。
3 GiB/swap0/CPU1/pids128、証明timeout120秒を維持した。本番受入は未達。
