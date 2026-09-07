# 組立て・本番受入れの未完条件

判定対象を明確にしたうえで、未実装の項目と未実施の検証を区別する。
`contracts/release-gates.json`は義務の一覧であり、state文字列をpassへ編集しても証拠にならない。

|項目|この版の状態|次に必要なもの|
|---|---|---|
|SUSE基盤選定|固定した別profile/調査資料|対象hardwareとminorの資格化|
|Config汎用モデル|実装ソース|Adaビルド/証明、全適用先adapter|
|Config native inventory|限定した実ファイル観測コード|全include/生成物/実行状態の認証観測|
|NVIDIA電源検査|exact capability純粋判定/CLI|RTX3090実機、adapter/running collector、失敗復帰試験|
|全ワーカーへの設定gate|generic SDK opt-in|呼出し方向/投影検査とmandatory配置|
|配布入力|実Python工具、署名/metadata/hash検査|元RPM署名、exact dependency closure、readonly cache|
|KIWI|XML出力工具|schema検査・imagebuild・通常/回復Secure Boot|
|Installer|Agama経路を設計|実profile/ISO/鍵・ディスクの安全なprovisioning|
|RPMDB/host /|native zypper所有を維持|完全移行は未実装、無理に二重管理しない|
|Remote manager HA|既存local管理まで|transport/availability/anchor運用接続|
|物理fencing/DBrestore|判定モデルと一部SDK|実backend/分断/restore試験|
|長期GC/巻戻し防止|既存SDKと方針|全volume復旧から独立した信頼状態、実GC接続|
|認定/支援|未認定|独立審査、site/vendor契約|

「他に必要な機能がない」と言うには対象業務・故障モデル・維持期間・保管要件を確定し、
この表の実装/接続を終え、全証拠を実行可能なreleaseへ結び付ける必要がある。
本版はそれを達成したものではなく、単にコンパイラ誤りを直せば全項目が完成するものでもない。
