# 採用コマンドの要求・計画同意・終端応答

2026-09-12 source実装。公開listener/本番planner/実native世代admissionは未接続。
未実装providerの代わりに許可を返す経路を用意しない。管理DEB 0.2.0とroot-preparation
0.13.0のsourceへ配布するが、実DEB/ISO受入・形式保証はリリース直前まで未実施。

`management_grammar.py`は採用コマンドを、副作用なしで解析する共通moduleである。
root decoderはローカル媒体/取得工具をimportしない。`package_cli.py`は既存のローカル処理を
維持し、稼働package操作の要求は`management_client.py`を使って固定の
`/run/niaos/package.sock`へ一度だけ送る。接続先不在は未送信、送信試行後の通信失敗は結果不明。
受信rootは`management_receiver.read_request`で元argvを独立に解析し、入力のpathをroot能力として
開かない。解決/入力読取は元actorと認証済み原本へ束縛したnative plannerの責務である。

要求は最大64KiB、canonical JSONのversion/command/arguments/languagesのみ。AF_UNIX SEQPACKET、
PASSCRED、SCM_CREDENTIALS/SO_PEERCREDとpeer pidfdで元processを結び付ける。未知field、
重複や非canonical入力、別actorと全添付FDを拒否する。言語設定は表示選択であり実行許可ではない。

変更計画はtrusted plannerがnative planとgenerationを決定し、その完全な意味からUTF-8表示を
作る。PlanConsentは最大1MiBの表示をroot所有memfdに置き、WRITE/GROW/SHRINK/SEALをすべて
sealして1個のFDで渡す。表示内容のhashとnative planのhashは別で、表示の完全性/正確性を
codecだけで証明しない。端末制御・bidi制御は拒否し、表示用の識別子はplannerでescapeする。

160byte offerはmagic、request16、plan32、generation32、presentation32、元BOOTTIME期限BE64、
表示byte長BE64、boot16、予約zero8。48byte replyは別magic、offer全体のSHA256、confirm1byte、
予約zero7。`pkgcore/src/pkg_plan_consent.*`は同じ厳格形式の純粋Ada codecである。
clientはroot credentials、FD所有者/seals/size/hash、boot/期限を検査して/dev/ttyへ表示する。
stdin/env/quiet/-Yは同意の代用にならず、入力済み文字をflushして明示のyesを受け取る。
非対話処理やGUI用の同意経路は未実装で、保存grantや暗黙承認では代用しない。

root側PlanConsentは非blockingの一度限りのoffer/responseを保持し、同じpeer/pidfd、
plan/generation/request/元期限をroot効果の全寿命で確認する。後続packet、切断、process終了、
期限切れで失効する。root Supervisorにはこの実objectが必須で、operator認証peerと同一socket
であることも確認する。同意はpolkit認証、供給/世代認可、署名付きnative grantの代わりにならない。
全provider・launcherによる統合は残件である。

終端応答はcommitted/refused/indeterminate/preview/read-onlyを区別する。request16と表示を含む
`NIARSL01`の固定headerで、committedは現在同意のある変更要求のみで成功になる。
root準備ACK、controller解放EOF、catalog確定、実boot成功を同一視しない。
committedを送れるのはnative catalogと全効果の独立な終端再照合が済んだ管理器である。

今回の範囲はAdaコンパイル、Python構文と6 moduleのstrict typing、gettext 123原文/7言語の
asset生成まで。挙動/通信/VM/攻撃的障害/形式証明の実行は延期した。root-supervisorの既存fixtureは
新同意交換に更新したが、人間の対話や本番plannerの保証にはならず、今回実行していない。
