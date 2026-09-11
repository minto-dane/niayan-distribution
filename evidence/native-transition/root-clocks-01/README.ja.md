# 原本時刻によるroot展開・配布packageの検証

対象source subject: `4230d1d819551dc90354ad75318b0e962963e2659f29a4b9a5a00739311f6d1f`。
判断はADR-0102、要求REQ-140。`report.json`と`executed-source-inputs.json`に実行入力を束縛した。

- `check-01.log`: 通常buildと独立wire 34 case。`sanitizer-01.log`: 同じcaseをASan/UBSanで確認。
- `vm-stream-02/result.json`: 直接buildしたworkerの正/負root展開と5拒否、計7 case。
- `vm-package-02/`: 0.2.1の別directory build、主DEB/dbgsymのbyte一致、導入したworkerの同じ7 case。
- `positive.tar` / `negative.tar`: 各10 entryの小さい検証入力。配布root/ISOではない。
- `source-checks.json`: 同一subjectで構造、syntax/local link、統合構造、license、生成CIを確認。

実root/dir/file/symlink/hardlinkのmtime/明示atimeを、readerを使わないPython整数nanosecondで
照合した。`negative-clocks`内に実観測値を残した。通常fileの読取前にstatを取り、
デバイスnodeはlstatだけで観測し開いていない。ctime/birthtimeは原本履歴であり実復元を主張しない。

`source-02-inputs.json`の23 package入力は現在の自作ソースと一致する。worker/testの7入力も一致する。
package標準試験から34 wire caseが実行される。主DEB/dbgsymのhashは`vm-package-02/package-sha256.txt`。
主DEBのhashは`a763fab2de27025e1a48fa1b8dcb541ba26166fd52bcf069409b374480d669f1`。
導入workerは`5201764b052db748fe6ee07d7c2df01bac1a2c5cbe773ac805374c7db5cbe655`。
service unit検査とsocketの非自動起動/非有効化も確認した。認可providerの完成という意味ではない。

初回KVM権限不一致は`vm-stream/`、古い版番号による比較停止は`vm-package-01/`へ保存した。
後者の両buildは0.2.0として成功しているが、比較/導入の成功とは数えない。
最終0.2.1の受入は別overlayで行った。失敗時の原本harnessも残した。

全ての重い処理は3 GiB/swap0/CPU1/pids128、各VMは2 GiB/1CPUで逐次実行した。
VM baseは読取専用、展開先は使い捨てtmpfs nodev/nosuid/noexecである。
`run-container.py`等は私有labからの実行記録であり、QEMU/SSHのruntime資産と秘密鍵はこの証跡へ含めない。
`report.json`にimage/artifact hashと制限を記録した。ELF、VM disk、CAS、秘密鍵、配布DEB自体は含めない。

全signed端点は形式検査であって実FSの全範囲復元保証ではない。永続媒体の電断、全root配置の直列化、
全DEB効果、managed認可、保持/復旧、実root/boot、完全置換ISO、全言語翻訳は未認定または未完である。
Ada・数学的入力・共有vendorは不変で、全suite/証明/旧カオスを反復していない。公開releaseも行っていない。
