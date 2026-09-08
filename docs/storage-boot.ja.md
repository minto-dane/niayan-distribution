# Nia OS ストレージ・起動・回復

> 保存した独自カタログ研究モデルの文書です。Debian 13の実配布方針は[現在の設計判断](decisions/0001-debian13.ja.md)を参照してください。この文書の機能が実イメージへ接続済みであるとは扱いません。

## 適用範囲

Nia OSのディスク上の永続ファイルシステムはXFSで統一する。UEFI用ESPはFAT32、`/run`と`/tmp`は容量上限付きtmpfs、proc/sys/devなどはカーネルの仮想ファイルシステムである。通常のrootは更新可能であり、一般のパッケージ更新を一律に次回起動へ延期しない。

これは製品仕様と配置検査の契約である。パーティション作成、鍵登録、UKIの実生成・書き込み、実起動の認定は別の工程である。

## ディスクとボリューム

本番参照構成は、独立した電源断保護付き装置を2台以上用い、各装置へ独立ESPを持つ。データ用領域はLinux MD RAID1 → LUKS2 → LVMの通常の厚いLV → XFSの順で構成する。薄い割り当てやスナップショットを必須としない。実装はWWN/serial、容量、partition UUID、既存用途の有無を認可した計画へ結び付け、デバイス名の推測で初期化しない。

LVは独立した復旧・容量制御単位であって、独立した物理故障領域ではない。同じRAIDや暗号化コンテナの故障は複数LVへ及ぶ。別ノード・別拠点のバックアップ、秘密鍵の独立回復、複数ESPの独立した起動試験が必要である。RAIDのコピー一致だけから、内容の真正性は判断しない。

XFSの形式はCRC付きv5、4096バイトブロックを対象とする。rmapbt、parent pointers、finobt、inobtcount、bigtime、reflinkを有効にした成果物を資格化する。セクターサイズ・実際のfeature bits・mkfs工具を固定し、通常カーネルとrescue工具の双方で読み書き・検査・復旧を試験する。機能の名前や工具の版番号だけから対応済みとは判定しない。ファイルシステムの縮小、強制修復、ログ破棄に依存しない。

## 状態の配置

正本は[配置契約](../contracts/state-domains.json)である。各独立領域は別の厚いLVとし、そのLV上のXFSを指定された場所へ必須マウントする。マウントが失敗した場合、親root内の同名ディレクトリへ書いて代用してはならない。

|領域|配置・回復単位|
|---|---|
|`/`、`/usr`、`/etc`|`nia-system` XFS。配布ファイルと設定の世代|
|`/var/lib/nia/catalog`|同じ`nia-system`内の通常ディレクトリ。別マウント不可|
|`/var/lib/nia/control`|`nia-control` XFS。意図・WAL・要求・結果不明を保持|
|`/var/lib/nia/trust`|`nia-trust` XFS。失効・受入世代を独立アンカーと照合|
|`/var/lib/nia/objects`|`nia-objects` XFS。認証済み原本・復旧入力|
|`/etc/nia/keys`|`nia-secrets` XFS。ノード固有の秘密情報|
|`/var/log`|`nia-logs` XFS。監査と診断。別障害領域にも送る|
|`/srv`|`nia-data` XFS。DB等が管理する業務データ|
|`/home`|`nia-home` XFS。利用者データ|
|`/var/cache`、`/var/tmp`|それぞれ独立XFS。再生成できる内容だけを置く|
|`/efi`|FAT32 ESP。署名付き起動・復旧成果物。秘密情報を格納しない|
|`/run`、`/tmp`|容量上限付きtmpfs。唯一の復旧入力を置かない|

`/var/lib/<service>`へ保存するサービスは、対応するデータ領域へbindする等の個別契約を持つ。全永続writerを分類する。`/var`全体を一括して巻き戻したり、一括して除外したりしない。

## 更新と復旧

世代とはNiaのファイル集合とカタログの対応を表す論理識別子である。XFSのUUIDやスナップショットと同義ではない。WALにはfilesystem UUID、root/catalog世代、transaction、plan、trust floorを結び付ける。

通常の更新では、認証済み原本・変更前像・属性・復旧情報を確保し、消費者と競合writerを制御してから実行する。意図の永続化、ファイルと親ディレクトリの同期、カタログ変更、終端再照合を一つの復旧プロトコルで扱う。異なるファイルやLVの更新が、XFSの内部ジャーナルだけで一括確定するとは扱わない。

OS全体の戻しは、Niaの逆方向計画または停止したsystem LVへの検証済みバックアップ復元で行う。control/trust/dataを一緒に戻さない。rootとcatalogの同一世代、継続中WAL、現在の失効情報を照合してから通常起動へ戻す。新しいWALを古いrootへ無条件に再生しない。

CASと稼働ツリー間で同一inodeを共有しない。異なるXFS間では検査済みコピーを使用する。同一FS内のreflinkを使っても、媒体の独立コピーにはならない。原本・鍵・冗長コピーがすべて失われた場合の完全復元を前提にしない。

## 健全性・監視

[XFS健全性仕様](xfs-health.ja.md)を適用する。metadata scrub、イベント監視、条件付きオンライン修復、媒体検査、認証済みカタログとの内容・属性照合を別の状態として記録する。全ボリュームについてUUIDと実マウントを列挙し、取りこぼしや二重監視を拒否する。

イベント受信・定期scrubは通常の運用条件とする。修復は、正確なkernel/xfsprogs/形式/rescue/方針の組を独立に資格化したセッションだけが行う。新しい制御状態が不明なら新規変更を保留するが、無関係な正常サービスを一括停止しない。

## 署名起動

systemd-bootとNia署名UKIを使用する。UKIのinitramfsにMD、dm-crypt、LVM、XFS、必要な認証・回復接続を含める。通常候補と独立rescue候補の双方で、使用するXFS機能とLUKS形式を扱えることを検査する。ESPは認可された更新時だけ書き込み可能とし、全ESPへの反映結果を別々に記録する。

UEFIがNia鍵を最初から信頼するとは仮定しない。認証済み鍵登録または物理的に統制した事前設定が必要である。Secure Bootの一時OFF、既存鍵の一括削除、initrdへの平文秘密鍵埋め込みを初期化手順にしない。TPM封印は正常・試験・rescue起動を含めて検証する。

## 電源管理

サーバー役割では自動suspend/hibernateを既定で無効とする。対話役割はドライバ、module種類、initramfs、通知経路、実効値、退避領域、復帰試験へ結び付ける。GPUの退避領域は暗号化された永続領域で予算を予約し、全GPU容量と同時使用を検査する。hibernateは専用の暗号化・resume・データ契約が資格化されるまで許可しない。

## 参照

- https://docs.kernel.org/filesystems/xfs/xfs-online-fsck-design.html
- https://docs.kernel.org/filesystems/xfs/xfs-self-describing-metadata.html
- https://man7.org/linux/man-pages/man2/fsync.2.html
- https://systemd.io/AUTOMATIC_BOOT_ASSESSMENT/
