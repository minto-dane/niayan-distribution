# 管理コマンドと更新メタデータの開発検査

公開操作の判断は[0003](../../../docs/decisions/0003-management-interface.ja.md)。
コマンド解析20、更新メタデータ7、移行5、ハードニング4、イメージ工具16の計52試験が成功。
source-checkは24工程の開発ソース検査であり、Ada実行・形式証明・新ISO受入ではない。
report.jsonは検査した入力digestとsource subjectを保持する。

実DEBは既存のniaos-defaults 0.1.0 all。元のniaos-integration .changesの
ソース・版・architecture・DEB hash/sizeを照合してurgency=mediumを観測した。
修正告知と緊急度の負のケースは人工fixtureで検査した。
署名済み告知の取得、稼働catalog、実行器、緊急修正、画面の接続は未完。
