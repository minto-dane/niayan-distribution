# 世代イメージの属性受入

未改変の上流工具で世代rootを生成する方法を調査した。
固定Debian 13のerofs-utils 1.8.6-1によるtar直接入力は、現時点で採用しない。
[判断](../../assurance/docs/engineering/adr/ADR-0066.ja.md)と
[実行証跡](../evidence/native-transition/generation-image-01/README.ja.md)を参照。

| 観点 | 実測結果 |
| --- | --- |
| USTARの通常内容・全permission bit・UID/GID・既出targetへのhardlink・特殊inode | 基本9 entryで一致 |
| GNU/PAXの長い名前と多言語名 | 試験入力でbyte名と内容が一致 |
| 前方hardlink・GNU負時刻 | それぞれ構築失敗 |
| ACL | 工具は成功したがaccess ACLがimageにない |
| PAXの短い小数部・負小数時刻 | 工具とfsckは成功したが時刻が不一致 |
| 再現性 | 同じ入力の4組でimage bytes一致。不一致属性まで再現される |
| 暗黙のroot・親directory | mode0777で生成。所有権と属性をnative assemblerが明示する必要がある |

生成器の終了値やfsckは、原本からの属性保持の代用にならない。
また、読取り専用filesystemのmtimeと、原本に記録された独立のatime/ctime/btime・
inode flagsは同じものではない。原本inventoryを保存することと、稼働時の意味を
実現することを別々に検証する。

今後の世代形式はrootの表現とdigestを明示的に版付けし、
package間の所有権・衝突、構成とmutable data、効果、認可、実mount/bootと復旧へ接続する。
既存の制御状態用ファイル操作は全体を緩めず、未対応属性を旧形式へ切り捨てない。

参考にした一次資料:

- [DebianのDEB形式](https://manpages.debian.org/trixie/dpkg-dev/deb.5.en.html)
- [mkfs.erofsのDebian 13 manual](https://manpages.debian.org/trixie/erofs-utils/mkfs.erofs.1.en.html)
- [fsck.erofsのDebian 13 manual](https://manpages.debian.org/trixie/erofs-utils/fsck.erofs.1.en.html)
- [erofs-utils v1.8.6の形式定義](https://github.com/erofs/erofs-utils/blob/v1.8.6/include/erofs_fs.h)
- [erofs-utils v1.8.6のtar reader](https://github.com/erofs/erofs-utils/blob/v1.8.6/lib/tar.c)
- [Linux v6.12のinode読取](https://github.com/torvalds/linux/blob/v6.12/fs/erofs/inode.c)

この検証は合成入力に限定される。全元DEB、kernel mount、bootの受入ではない。
