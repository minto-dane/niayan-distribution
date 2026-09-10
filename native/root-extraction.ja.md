# 非公開rootを実ファイルへ展開する内部worker

`native/worker/root_extract.c`は保持root tarを空の非公開領域へ展開する、非setuidの内部実行物である。
既存SDKのUID0拒否を解除せず、公開コマンドや別のpackage writerを追加しない。
通常の管理コマンド・認可済み公開計画からの呼出しは、引き続きサービスへ接続する必要がある。

## 呼出し契約

実UIDと実効UIDの双方を0とする保護されたサービスだけが呼ぶ。FD 3は読取専用の通常tar、
FD 4はroot所有・0700のprivate staging親directory。親の`root`はroot所有・0700・空でなければならない。
rootには排他flockを保持し、実mountのnodev/nosuid/noexecを検査する。稼働rootへの展開はしない。

引数は検証済みtarのSHA-256、正確なbyte長、正確なentry数、CLOCK_BOOTTIME基準の期限ms。
最大8 GiB、524,288 entry、600秒。CASのhash文字列だけを実行認可として扱わない。
呼出し側は同じwriter予約で、NIAGEN05/NIAROOT1・catalog/closure・元DEB・論理所有権・供給・
site効果契約を再検証し、期待値とFDの取得を束縛する義務を持つ。この本番adapterは未実装である。

workerは空rootへchroot/chdirし、外側directory FDと不要FDを閉じる。chroot単独をsandboxとせず、
no-new-privileges、dump禁止、必要な六つのinode操作capability、syscall ABIを検査するseccomp、
メモリ512 MiB・FD64・単一ファイル8 GiB・wall期限を併用する。exec、process生成、network socket、
mount/namespace変更等を禁止する。外側サービスはさらにcgroupと保護された親領域を維持する。
amd64を検証対象とし、aarch64のABI定義は未実行。他のABIは明示実装までbuildを拒否する。

## ファイルと属性

libarchiveのtar読取とdisk writerを使い、通常ファイル、directory、symlink、hardlink、
character/block device、FIFOを扱う。親の自動生成と危険なpath解決を拒否する。
展開中と検証時の再読の全入力をstreamでhashし、tar終端の後も指定byte長まで照合する。
検証用の全属性cloneは保持せず、entryごとの内容digestだけを保持してメモリを有界にする。
入力のhash不一致、entry数違い、library警告、属性未対応を成功にしない。

`linux-inode-v1`では数値UID/GID、全mode、mtime/明示atime、ACL、宣言xattr、set/clear flags、
link先・hardlink inode、device番号、全通常ファイルの長さと内容hashを読み戻す。
通常ファイルの照合はO_NOATIMEで行い、symlink読取で変わるatimeは復元する。
既存の展開rootの時刻は子作成後にFDから確定する。uname/gnameからホストの名前解決はしない。
PAXのUTF-8とbinary名は、利用者のUI localeから独立したC.UTF-8で処理する。
LOCPATH/GCONV_PATHを破棄し、必要なlocale資産をchroot前に読む。

ctimeとbirthtimeはLinuxの通常ファイル操作で任意の原本値へ設定する属性ではないため、
元tarの履歴として保持する。実inodeのそれらを原本と一致したとは報告しない。
新しいkernel/LSMが付ける未宣言xattrやラベルは別のsite policyの対象で、宣言xattrだけで
MAC状態全体を認定しない。表現できないUID・mode・ACL・flagsを黙って丸めない。

全検証とsyncfs後に、言語非依存のJSONで`extracted`、profile、hash、entry数、`published:false`を返す。
これ自体は署名付きreceiptでも公開成功でもない。終了codeと完全な結果の両方を照合する。
容量不足・期限・停止・不一致では部分treeが残り得る。再使用は空条件で拒否し、controllerが
隔離世代を破棄または再構築する。既存accepted root/stateを書き換えたり、失敗を再初期化で隠さない。

## buildと受入

固定開発imageのgcc、libarchive-dev、libsodium-devで`make native-worker`を実行する。
`make native-worker-check WORKER_TEST_BASE=<専用mount>`は使い捨てのprivileged VMで実行する。
試験は全7種類と数値属性、ACL/xattr、日本語と非UTF-8の名前、root時刻、入力/件数/期限/既存treeを確認する。
device nodeはlstatで確認し、開かない。Distroboxの外側でmknodが拒否される場合、その実行を受入成功にしない。

tmpfs上の展開成功を永続媒体の電断試験と呼ばない。保護された実世代bank、同じ認可/保持閉包からの
worker起動、ディスク容量予約、controllerの再開・回収、全DEB効果、実mount/bootと完全置換ISOが残る。

一次資料: [libarchive disk writer](https://github.com/libarchive/libarchive/blob/master/libarchive/archive.h)、
[読取と展開のAPI](https://github.com/libarchive/libarchive/wiki/Examples)、
[chrootの制約](https://man7.org/linux/man-pages/man2/chroot.2.html)、
[tarの文字コード処理](https://github.com/libarchive/libarchive/blob/v3.7.4/libarchive/archive_read_support_format_tar.c)。
