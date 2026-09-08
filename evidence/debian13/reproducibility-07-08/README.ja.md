# ISO 07/08の再構築比較 — 不一致

2回とも新しいbootstrapとインストーラー取得から構築を完了した。入力manifestは一致し、ISOはともに3,640,655,872 bytes。認証済みDEBキャッシュと、独立再ビルドで検証済みの独自DEBは再利用した。[比較工具の結果](iso-comparison.json)は失敗。07のVM受入6項目は成功しているが、この比較を成功とは扱わない。

ISO内部のチェックサム一覧では、差はLiveの`filesystem.squashfs`に限定された。カーネル、Live initrd、通常・GUIインストーラー、2,239件のパッケージ一覧は一致した。両SquashFSの作成時刻は2026-09-07 00:00:00 UTC、inode数は216,071で一致したが、圧縮後の内部サイズは2,832,435,963 bytesと2,832,436,700 bytesだった。

完成した2つのSquashFSをビルダーVM内で`loop,ro,nosuid,nodev,noexec`としてmountし、`rsync -aHAXnic --delete`で内容・時刻・権限・所有者・ハードリンク・ACL・拡張属性をdry-run比較した。[全出力](squashfs-rsync-07-08.txt)に現れた差は`var/cache/swcatalog/cache/C-local-metainfo.xb`だけだった。比較後は両mountを解除した。

後続レシピでは、AppStreamが再生成する`var/cache/swcatalog/cache/C-*.xb`を、APTの2つのキャッシュと同じくlive-build標準のrootfs除外設定に加える。Debian提供の再現性hookにもAppStreamキャッシュの整理があるが、ここでは実行ファイルを一時wrapperへ置き換える方式は使わず、圧縮対象から除外する。AppStream・live-build・コンポーネントの上流ソースを変更しない。

`build-record-08/`は生成物のhashと実設定の抜粋で、参照されるISO・DEB・udeb自体はGit外に保管する。この記録は後続修正の成功や本番・実機認定を意味しない。
