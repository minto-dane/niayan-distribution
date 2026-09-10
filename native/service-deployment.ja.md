# 内部root準備サービスの配備

`packaging/root-preparation/`はDebian 13向けの`niaos-root-preparation`ソースパッケージである。
専用account、socket、service、保護mountと設定を一緒に管理する。workerはDebianの
libarchive/libsodiumへ動的linkする。上流ソースの変更、第二の導入済みDB、公開管理コマンドの追加は行わない。
このパッケージの導入は、独立認可provider・全DEB効果・起動切替を完成させるものではない。
現在の配布対象は受入済みのamd64だけである。他CPU向けのビルド・syscall ABI・実機受入は別工程とする。

## 再現ビルド

repository直下から新しい出力directoryへ、選択した自作ソースをそのまま出力する。
親directoryはあらかじめ用意し、既存の出力を上書きしない。

```sh
make -C distribution native-service-source SERVICE_SOURCE=/絶対path/新規source
cd /絶対path/新規source
DEB_BUILD_OPTIONS=parallel=1 dpkg-buildpackage -us -uc
```

ビルド依存は`debian/control`、実際の版は生成された`.buildinfo`に記録する。
固定したDebian 13 builderと`dev/run-limited.sh`の3 GiB/swap0/CPU1/pids128制限を使う。
`source-inputs.json`は元の相対path・mode・SHA-256を保持する。ビルド場所をdebug情報から
正規化し、主DEBとdbgsym DEBを別directoryで比較する。署名・公開鍵配備・全環境での再現性は別条件である。
開発builderのdpkgはこの配布成果物を検査する工具であり、稼働NiaOSの代替管理入口として採用しない。

## 配置と明示的bootstrap

|対象|所有と用途|
|---|---|
|`nia-pkg`|sysusersが割り当てる非root固定account、nologin。数値UIDは決め打ちしない|
|`/etc/niaos/root-preparation.json`|root:root 0600、conffile。v2で`client_user=nia-pkg`を指定|
|`/var/lib/niaos/core`|nia-pkg専用0700。native SDKのCASはこの下の`store`|
|`/var/lib/niaos/roots`|root専用0700。nodev/nosuid/noexecのbind mountを必須とする非公開bank|
|`/run/niaos/root-preparation.sock`|root:nia-pkg 0660のseqpacket。socket activationでFD 3を渡す|
|`/usr/libexec/niaos/`|root管理のdaemonとELF worker|

標準debhelperのsysusers処理でaccountを作る。compat 13では`dh_installsysusers`を明示的に
呼ぶ。unitは`dh_installsystemd --no-enable --no-start`で導入する。インストール時にCASやbankを
初期化せず、socket/serviceも有効化・起動しない。設定変更を無条件に上書きしない。

製品installerは、利用者の導入先と初期化意図を確認した後、次の順序を所有する必要がある。

1. root管理の`/var/lib/niaos`の下へ上表の二つの専用directoryを用意する。
   既存状態・symlink・予期しない所有を新規状態として採用しない。
2. `nia-pkg`のnative SDKで空の`core/store`へ`MC_Store.Initialize`を実行する。
   手作業で`store.lock`だけを作らない。このSDKを呼ぶ製品installer/controllerは未接続である。
3. `var-lib-niaos-roots.mount`を開始する。unitは既存directoryを必須とする。
4. rootで内部工具を一度だけ呼ぶ。
   `python3 -I /usr/libexec/niaos/root_bank.py --config /etc/niaos/root-preparation.json --provision-bank`
   既存の空保護mountだけを対象とし、CASは初期化しない。エラー時も初期化済み・部分状態が
   残り得るため、削除や再実行で成功扱いにせず独立復旧へ渡す。
5. 独立供給・世代認可policyと、採用workerの期待SHA-256をcoreへ配備した後に
   `niaos-root-preparation.socket`を有効化する。サービスが報告するhashから自己承認しない。

これは内部配備契約であり、一般利用者向けの別パッケージ管理CLIではない。
受入VMでは手順2を既存の人工fixture driverで実行する。本番認可としてそのfixtureを導入しない。
設定v1の数値`client_uid`も引き続き読める。v2のaccount名は起動時に実UIDへ解決し、
未存在・root・型不正・余分なkeyを受け付けない。accountを削除して同UIDを別用途へ再利用しない。

## 実行の制限と停止

serviceはrootとして必要な七つのcapabilityだけを保持し、workerはchroot後に六つへ減らす。
NoNewPrivileges、namespaceの変更禁止、AF_UNIX限定、kernel/cgroup保護を併用する。
通常のfilesystemは読取専用で、書込先としてbankを指定する。CASは読取専用のpathとし、
実予約はcoreから渡された同じOFDで保持する。`/tmp`と`/var/tmp`も空の読取専用tmpfsにする。

`/dev`にはパッケージ内の四つの通常fileを持つdirectoryを読取専用bindし、その上へ
null/zero/random/urandomだけを読取専用bindする。これによりdevice inodeを復元する
CAP_MKNODを保持しつつ、通常のblock deviceを直接見せない。PrivateDevicesは必要なcapabilityを
除くため使用しない。展開先bankはnodevで、作成したdeviceをそこで利用しない。
このmount設定を任意rootコードに対する完全な隔離と表現しない。worker自体のFD閉鎖・seccompと
入力照合、信頼されたdaemon/controllerも引き続き必要である。

systemd 257ではkernel/cgroup保護が加えるAPI mountが`TemporaryFileSystem=/dev`より優先される。
その組合せは実VMで/devが隠れなかったため採用しない。根拠は
[systemd 257のnamespace実装](https://github.com/systemd/systemd/blob/v257/src/core/namespace.c)。
一般的な設定契約は[Debian 13 systemd.exec](https://manpages.debian.org/trixie/systemd/systemd.exec.5.en.html)を参照。

unit全体はMemoryMax=1 GiB、swap0、CPUQuota=100%、TasksMax=32、FD64、core dump無効。
workerの既存512 MiB/期限/出力上限も維持する。停止はcontrol-group全体へ行い、OOMでもunit全体を
停止する。自動restartで処理を再送しない。workerや設定の更新時は、認可側を休止し、socketとserviceを
停止してから成果物と独立期待hashを更新する。明示的再開後に履歴を確認する。自動bootstrapしない。

欠損状態でのsocket activationはsystemdのtrigger制限に達するとsocketも停止する。
復旧時は両unitを停止し、正しい既存inodeを独立手順で復元してから両unitをreset-failedする。
systemd 257ではreset-failedだけではsocketのtrigger counterを消さないため、既定の2秒のwindowも
経過させてから明示的に再開する。制限を無効化しない。
[systemd.socket](https://manpages.debian.org/trixie/systemd/systemd.socket.5.en.html)と
[257のreset実装](https://github.com/systemd/systemd/blob/v257/src/core/socket.c)を参照。

通常起動はbank.json/bank.lock/CAS lock/設定の欠損を拒否する。再起動後の`inspect`は保存履歴であり、
物理再検証・公開・boot許可ではない。未完intentや切断を未実行と決め付けない。

## 受入境界

`worker/check_service_deployment.py`は使い捨てsystemd VM専用である。インストールされたunitと
動的割当accountを使い、元人工DEBから実native世代を作ってELF workerまで接続する。
二重初期化拒否、mount/device view、資源制限、再起動後の履歴、設定と二つのlockの欠損拒否を確認する。
ホストや稼働OSでは実行しない。公開済みISO 09の受入をこのパッケージへ流用しない。
容量予約、物理再検証/回収、独立認可/供給provider、全DEB効果、実boot、完全置換ISOは引き続き未完である。
