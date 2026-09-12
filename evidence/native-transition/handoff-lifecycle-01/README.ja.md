# root handoffの状態・解放と検証工具の受入

2026-09-12 UTC。source subject: `ce4255b5980cd2c280046757074c693e983ebbd211b8ac006d707037cc483ec8`。ADR-0119、REQ-157/HAZ-143/FAULT-156。
本番接続・全runtimeの形式証明は未完。

実Channelの状態を有限制御へ集約し、I/O前の試行記録、失敗/閉鎖後の再利用禁止、
所有FD解放のOSError後も残るFD/pidfd/socketを解放する処理を実装した。
同じFD番号をcloseし直さず、解放失敗後に成功応答を送らない。
boottimeは整数nsで扱い、pollの呼出し数を1200へ制限した。

固定containerで10項目の障害/制御検査と、実root/非root・pidfd・SCM・Ada往復15項目が成功した。
EIOは自分の実FDをcloseした直後に注入し、その番号を実際に再利用して誤解放しないことを確認した。
本当の媒体障害、kernel故障や任意の非同期中断の検査ではない。
入力解放エラー/子監視FDエラー/閉鎖/受信失敗/応答待ち中取消/poll予算を含む。
C/Adaの425ビルド入力が前回と同一で、既存実行物のhashを照合して再利用した。
今回のcompile件数やsanitizer実行件数に数えない。

実transition関数と独立した履歴counterの全到達15構成、29許可辺・76拒否辺を探索した。
深さ上限は設けず、失敗後再開/受信前completeを許す二つの負の対照も検出した。
assertを無効にするPython最適化モードは拒否した。
これは有限制御と履歴の検査であり、Python/OS/I/O/全資源寿命の形式証明ではない。

root_handoffと検査器の2ファイルに、mypy 1.15.0-5 strictとAny/到達不能制約を適用し成功した。
未使用recvmsg addressはobjectに限定し、type ignore/castは使わない。
初期の型診断ログは診断履歴であり、その時点の全変更入力snapshotは保持していない。
最終の正確な入力はsource-inputs/new-image-check-inputs/runtime-inputsで区別する。

正本dev/Containerfileとpackages.txtから開発imageを実際に構築した。
image: `sha256:76d5c00dfa833ce7ae67a192c5663d9bcd5c4104153f5933431dae88c097918c`。
Debian base digestと署名付き2026-09-07 snapshot、CBMC/mypyの固定版を使用した。
3 GiB/swap0/CPU1/pids128、900秒・空き3 GiB停止条件を維持し、約257秒で成功した。
最小空き容量はimage-build-report.jsonに実byteで保持する。
新imageのnetworkなし非root実行で型/有限制御検査と、実wire関数のCBMC208条件が成功した。
CBMC工具hash/仮定/入力/結果はimage-c-proof/report.json、全工具package版はimage-packages.txt。
OSイメージの再現性試験やremote CI、全suiteの新規受入ではない。

構造/参照/lint/license/生成CIも成功。CI経路へ必須チェックとmypy依存を追加した。
現在供給/世代admission、正確な同意、root session/独立観測と物理遮断の製品接続は未完。
C全体の厳格規則適合、完全置換ISO、実root/boot切替/復旧、全DEB効果、全言語翻訳も未完。
