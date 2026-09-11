# 専用bankの配備と再起動後の識別

0.5.0の内部storage installerは、明示的に選択されたGPT partition上のext4だけを新規bankとして使う。
パーティション作成・formatは行わない。導入先の保守環境で、installerが対象diskとmount操作を排他的に
管理し、空のext4を用意してから既存の`storage_bootstrap.py --initialize`を呼ぶ。
通常のデスクトップや開発ホストを導入先にしない。旧bind bankの自動移行は提供しない。

## 選択情報

`/etc/niaos/root-bank-device.json`はroot:root 0600で、protected parentに配備する。必須fieldは次の通り。

|field|値|
|---|---|
|`version`|整数1|
|`partition_uuid`|小文字の正規GPT partition UUID|
|`filesystem_uuid`|小文字の正規ext4 UUID|
|`size_bytes`|選択したpartitionの正確なbyte数、32 MiB以上|

余分なkey、重複key、boolによる整数代用、非正規UUIDは拒否する。32 MiBは形式上の下限であり、製品に
必要な容量ではない。実root・更新・回復世代に必要な容量計画はinstallerが別途行う。
`/dev/disk/by-partuuid/…`は検索入口であり信頼根ではない。root管理のparentからblock FDを保持し、
BLKGETSIZE64とcacheを使わないblkid低level probeで容量・filesystem type/UUID・GPT scheme/UUIDを
再確認する。whole disk、共有subtree、現在の`/`のdevice、初期化時の既存mountは拒否する。
raw deviceへ書けるroot/disk group等はinstaller/controllerと同じ特権管理境界にある。

識別子は暗号学的なdevice認証ではない。UUIDと内容を複製したdiskの識別、hotplug/device再割当て、
特権mount/raw block書込の排他、LUKS/device-mapper/RAID等の別storage profileは未認定である。

## 初期化と通常起動

既存の排他的bootstrap intentへ選択情報全体のSHA-256を加える。既存core/bank/記録やmount drop-inは
上書きせず拒否する。native CASを正規initializerで作った後、installer所有の
`/etc/systemd/system/var-lib-niaos-roots.mount.d/50-device.conf`をO_EXCLで作成・同期する。
Whatには選択したPARTUUIDだけを出力し、Type=ext4、Options=ro,nodev,nosuid,noexecとする。
配布側のunitは未配備deviceを指定して拒否し、bind mountへfallbackしない。

mount後はFDのdeviceとext4 root inodeを確認する。空のroot又は空の`lost+found`だけを初期状態として扱う。
recovery内容や既存bankを削除しない。初期化区間だけ明示的にread-writeへ変更し、rootを0700へ設定して
既存bank provisionerを呼ぶ。finallyでread-onlyへ戻し、現在mountの照合に成功した場合だけ完了記録を保存する。
失敗や電源断で部分状態は残り得る。自動再初期化・rollback・fsck・記録削除は行わず、独立復旧へ渡す。
finallyはSIGKILLや電断には実行されない。再起動時のunitはread-onlyとし、完了記録なしにserviceを開始しない。

root準備serviceは`niaos-root-bank-check.service`を先に要求する。oneshot検査は選択情報・drop-in・
初期化intent/完了記録のhash、現在のblock deviceとmounted root、保護mountとbank記録の存在を照合する。
新しい起動ごとに検査し、結果を永続boot許可にしない。準備service自体へCAP_SYS_ADMINやblock device viewを
追加しない。検査serviceだけがraw deviceをread-onlyでprobeし、CAP_DAC_READ_SEARCH、128 MiB、swap0、
CPU1、Tasks8、起動45秒で制限する。kernel I/O待ちの厳密な終了時刻は保証しない。

unitは導入時に自動有効化しない。通常のmount開始はread-onlyである。初回の空bankは[root supervisor session](root-session.ja.md)で準備できる。
本番admission/native SDKとの接続、slot管理と外部writerを含む全寿命の排他は引き続き必要である。root準備serviceの
手動有効化だけで実展開・公開・boot切替が完成したとはしない。

## 検証

`worker/check_bank_device.py`は使い捨てVMの明示partitionで実native initializerと導入済みunitを使う。
選択欠損/UUID/容量不一致、既存/未完状態と再初期化の拒否、read-only再起動、guard経由のservice開始、
選択変更によるservice拒否とbank lock欠損時の非修復を確認する。試験自身の明示復元を製品復旧とは数えない。
既存のサービス/SDK試験では`check_service_deployment.py --device-plan /etc/niaos/root-bank-device.json`を指定する。
その試験は独立に用意した新規partitionのplanを必要とする。

完全置換ISOのpartition recipe/UI、認証済みcontrollerとbank slot管理、全DEB効果、実root/boot切替・復旧は未完。

根拠: [Debian 13 blkid(8)](https://manpages.debian.org/trixie/util-linux/blkid.8.en.html) のcacheを迂回するprobeと
PART_ENTRY field、[systemd.mount(5)](https://manpages.debian.org/trixie/systemd/systemd.mount.5.en.html) のdevice mount依存関係。
