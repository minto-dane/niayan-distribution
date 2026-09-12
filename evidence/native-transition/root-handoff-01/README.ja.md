# 非root世代SDKとroot間の限定handoff検証

2026-09-12 UTC。source subject: `462da7431ca1adb554a012199e26649b33bb3f3a0c785fe34590d345bbda53f6`。
ADR-0118。新しい公開管理入口は追加していない。本番接続・全体の形式検証は未完。

実kernel資格情報、pidfd、SCM_RIGHTSと実FD予約を使う15項目が成功した。
通常、scope相違、余分FD/control切詰め、子孫送信者、応答不正/過大/余分FD、
無応答、完了前取消、forkしたhandle、SO_PASSCREDなし、Ada往復、root worker拒否を含む。
transport-02はPython注釈追加前、sanitizerは最終Pythonに対する実行である。
sanitizerの15項目のうちAda execは非instrumentedで、残るC呼出しがASan/UBSan対象。
Python全体のleak検査は無効で、address/UB異常は停止し、FD数と借用FD寿命を別に検査した。

3 Ada mainのcompileと実行、既存v5/v6世代処理の認可前後とtransport異常の回帰確認が成功した。
425個は照合したビルド入力集合であり、全425unitのcompile件数ではない。
export後の差分は生成CIのsetup/test登録だけ。artifact-check.jsonに実行物hashを保持する。
初回の取消後RSTを失敗扱いしたfixtureとprivate CAS権限不足のfixture失敗も保持した。
修正後はEOF/RSTの正当な取消結果とumask077を使う。runtimeの拒否条件を緩めていない。

root supervisorによる現在供給/admission、正確な同意、実root session、独立再観測、
取消の物理遮断への接続は未完。テストの成功callbackを本番認可に使用しない。
C transportの全形式検証と厳格規則適合、特権Pythonの厳格型検査/形式的対応も未完。
純粋wire関数の限定証明は../../implementation-assurance/initial-01/を参照する。
構造/参照/lint/license/生成CI検査は成功。VM/ISO/remote CIは今回実行していない。
全重工程は3 GiB/swap0/CPU1/pids128で直列実行した。SHA256SUMSはこの証跡集合のみを照合する。
