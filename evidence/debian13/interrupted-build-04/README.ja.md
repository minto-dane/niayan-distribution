# 構築04の中断記録

2026-09-08。ISO完成前に、専用ビルダーVMを通常の`systemctl poweroff`で停止した。SSHビルド呼出しは255で終了し、成功・再現性・起動受入として扱わない。

新規bootstrapにはCA証明書が正しく入った。しかし、生成された`LB_PARENT_MIRROR_DEBIAN_INSTALLER`はHTTPのbootstrapミラーを継承し、明示した`LB_MIRROR_DEBIAN_INSTALLER`のHTTPS指定とは異なっていた。取得ログでもインストーラー本体のHTTP取得を確認した。

後続レシピは`--parent-mirror-debian-installer`も明示し、生成された設定を読み戻すassertionを加える。上流live-buildのソースを変更しない。ここには当時の入力manifest・実設定・中断ログを残す。
