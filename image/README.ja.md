# Debian 13イメージの構築

開発版。既存の7コンポーネントを改変せずにDEB化し、Debian 13 Trixieの公式パッケージと組み合わせる。[設計判断](../docs/decisions/0001-debian13.ja.md)。

amd64・KDEの実ISOについて[構築と6項目のVM受入記録](../evidence/debian13/accepted-09/README.ja.md)を保存している。同じ入力からのISO 09/10が実バイト列で一致し、[対応ソース1,415組の収集・補完・照合](../evidence/debian13/accepted-09/source-collection/README.ja.md)も完了した。下記手順の記載だけを成功結果とはせず、対象hashを確認する。

## 入力と成果物

`Containerfile`はビルダーのベースdigestと署名付きAPT snapshotを固定する。`lock.json`が配布対象・snapshot・時刻の記録、`auto/config`がlive-buildの設定、`../packaging/integration`がNiaOS固有DEBの正本。設定は上流の公開された拡張機構で適用する。

debootstrapのincludeオプションでCA証明書を最初の最小環境にも含め、HTTPSを使う後続工程で証明書検証を維持する。bootstrap入力を変更した場合は古いbootstrap stage cacheも破棄して再構築する。APTの再生成可能な`pkgcache.bin`と`srcpkgcache.bin`は、内部時刻による差を避けるため標準の`config/rootfs/excludes`でISOから除外する。AppStreamの再生成可能な`var/cache/swcatalog/cache/C-*.xb`も同じ仕組みで除外する。APT・AppStream・live-buildのコードは変更しない。通常mirrorの変化するAPT索引はISOへ残さず、起動後に通常の署名検証付き`apt update`で取得する。

インストーラー本体の取得では、live-buildが参照する親ミラーも`--parent-mirror-debian-installer`でHTTPSに固定する。`auto/config`は生成後の実設定を読み戻して確認する。署名付きAPTで検証されるDEB/udebと、HTTPSで取得するインストーラーのkernel/initrdを区別して記録する。

live-buildのTrixie既定値は`apt-mirror-setup`を除外するため、そのままではインストール時のミラー設定が提供されない。`prepare-installer.py`は固定snapshotの署名付き索引から指定版の公式udebを取得し、標準の`config/packages.binary/`入力へ配置する。上流スクリプトや除外リストを編集しない。参照: [live-buildのインストーラー生成処理](https://salsa.debian.org/live-team/live-build/-/blob/master/scripts/build/installer_debian-installer)、[Debian apt-setup](https://sources.debian.org/src/apt-setup/1%3A0.198/)。

`prepare.py`は新しい作業ディレクトリだけを作る。既存ディレクトリや未コミットのコンポーネントを拒否し、各repoの固定commitとソースhashを記録する。コンポーネント本体・vendor・Makefileは書き換えず、作業コピーにだけDebianパッケージングを加える。

DEBとデバッグパッケージ、`.dsc`、ソースtar、`.changes`、`.buildinfo`は`packages/`へ生成する。ISOとlive-buildのパッケージ一覧は`live/`へ生成する。ISOをGitへ追加しない。公開前に対応する上流ソース・ライセンス、生成物hash、連絡先と署名・更新運用を揃える。

## 通常のroot権限を持つビルド環境

以下は必要なマウントとデバイス作成を許可されたビルダー向けの手順。このDistroboxでは次節のVMを使う。workspace直下で実行し、単一の重い処理だけを動かす。イメージ構築にはネットワーク、package buildとVM試験にはネットワーク不要。最低20 GiB以上の空き領域を用意し、デスクトップ・ソース保管分に応じて増やす。

```sh
python3 distribution/image/prepare.py --output "$PWD/.work/trixie" --desktop kde
sh dev/run-limited.sh sudo -n podman build -f distribution/image/Containerfile \
  -t localhost/niaos-image-builder:20260908 .
sudo -n podman run --rm --network=none --user "$(id -u):$(id -g)" \
  --memory=3g --memory-swap=3g --cpus=1 --pids-limit=128 \
  -e HOME=/tmp -v "$PWD/.work/trixie:/build" \
  -v "$PWD/distribution/image:/source:ro" \
  localhost/niaos-image-builder:20260908 sh /source/build-packages.sh
sudo -n podman run --rm --network=none \
  --memory=3g --memory-swap=3g --cpus=1 --pids-limit=128 \
  -v "$PWD/.work/trixie:/build:ro" -v "$PWD/distribution/image:/source:ro" \
  localhost/niaos-image-builder:20260908 sh /source/test-release.sh
sudo -n podman run --rm --network=slirp4netns --cap-add=SYS_ADMIN \
  --security-opt apparmor=unconfined --security-opt seccomp=unconfined \
  --memory=3g --memory-swap=3g --cpus=1 --pids-limit=128 \
  -v "$PWD/.work/trixie:/build" -v "$PWD/distribution/image:/source:ro" \
  localhost/niaos-image-builder:20260908 sh /source/build-live.sh
```

`--desktop`は`kde`・`gnome`・`server`。最初の受入対象はKDEで、選択肢の存在を全ての受入成功とは扱わない。GNOMEとKDEを同時にイメージへ導入しない。Liveユーザーは`niaos`、パスワードはDebian Live標準の`live`。Live専用で、インストーラーで作る永続ユーザーのパスワードとは別である。

KDEでは標準KConfigの`/etc/xdg/kwinrc`でFcitx 5をWayland入力メソッドに選ぶ。新規ユーザーの`.xinputrc`は、KDE WaylandではKWinに起動を任せ、X11ではim-configを使用する。これは[FcitxのWayland手順](https://fcitx-im.org/wiki/Using_Fcitx_5_on_Wayland)に沿った設定である。既存ユーザーの設定は上書きしない。既存DebianユーザーへDEBだけを追加する場合は、KDEの「仮想キーボード」でFcitx 5を選び、Waylandセッションではim-configによる二重起動を避ける設定を別途行う。

## このDistroboxでは使い捨てVMを使う

Distrobox内のユーザー名前空間では、作業領域に通常のデバイスノードを作れない。APTのchroot内で`/dev/null`が通常ファイルになる問題を実際に確認した。再帰的な最小`/dev`マウントで小さい取得試験は成功するが、標準の全イメージ工程には通常のroot環境を使う。live-build・debootstrapのソースやマウント処理は変更しない。

`builder-vm.json`にDebian公式cloud imageの固定URLとSHA-512を記録する。SHA512SUMSはHTTPSで取得したもので、cloud imageの独立したOpenPGP署名は提供されていない。署名検証済みと表示しない。VM内で導入するパッケージと配布イメージのDEB入力は、Debianの署名付きAPT snapshotで検証する。

`prepare-builder-vm.py`は取得済み`base.qcow2`のhashを検証し、新規の80 GiB sparse overlayとNoCloud seedを作る。既存VM状態への上書きを拒否する。公開鍵だけをseedへ入れ、秘密鍵はGit外の専用ディレクトリで管理する。`run-builder-vm.sh`はKVM・2 GiB・1 vCPUで起動し、SSHはホストの127.0.0.1:22222だけで待ち受ける。一般公開鍵・本番資格情報・ホストdiskは渡さない。

1. Git外の新規VMディレクトリへ固定cloud imageを`base.qcow2`として取得し、専用のEd25519鍵を`ssh-keygen`で生成する。
2. ビルダーコンテナにVMディレクトリを`/vm`、`image/`を`/source:ro`としてmountし、非rootで`python3 /source/prepare-builder-vm.py --directory /vm --public-key /vm/ssh-key.pub`を実行する。
3. 同じcontainerに`--device /dev/kvm --network=host`を指定して`sh /source/run-builder-vm.sh`を実行する。VM全体を`dev/run-limited.sh`の外側kernel制限へ入れる。
4. SSHの専用`UserKnownHostsFile`を使い、最初の接続後は`StrictHostKeyChecking=yes`で接続する。`image/`をVMの`/source`、`release/`を`/release`、準備した作業ディレクトリを`/build`へコピーする。
5. VM内で`sudo sh /source/provision-builder.sh`、続けて`sudo sh /source/build-live.sh`。再構築で設定を変えた場合は`--clean`を使用する。
6. 生成物とログをホストのGit外の成果物ディレクトリへコピーして、VMを通常のpoweroffで停止する。別VMでISO受入を行う。

この環境の入れ子Podmanは、既存ストレージを保持して次のprefixを使用した。

```sh
sh dev/run-limited.sh sudo -n podman \
  --cgroup-manager=cgroupfs --events-backend=file --storage-driver=vfs \
  --root /home/nia/devbox/niaos/.work/podman-root \
  --runroot /home/nia/devbox/niaos/.work/podman-session-run \
  --tmpdir /home/nia/devbox/niaos/.work/podman-session-tmp --transient-store \
  run --rm --cgroups=disabled --network=host --user 1000:1000 --device /dev/kvm \
  -v /home/nia/devbox/niaos/.work/distro-builder-vm:/vm \
  -v "$PWD/distribution/image:/source:ro" \
  localhost/niaos-image-builder:20260908 sh /source/run-builder-vm.sh
```

`--cgroups=disabled`は外側のkernel制限内だけで使用する。3 GiB・swapなし・CPU 1コア分・128プロセスの読み戻しが失敗したら実行しない。VM起動中に別の重い検証を重ねない。ビルダーVMは80 GiBの最大論理容量を持つが、実際の使用量は増加するため、ホストの空き容量も監視する。仮想diskは`discard=unmap`を有効にしており、VM内の`sudo fstrim /`で削除済み領域をホストへ返せる。

## VM受入

KDEの一括受入は、ビルダー内で`python3 /source/test-suite.py --iso <ISO> --output <新規ディレクトリ>`を実行する。BIOSと日本語入力、UEFIとAPT取得、Secure Boot、UEFIオフライン導入、BIOSオンライン導入、導入済みディスクのSecure Bootを必ず順番に実行し、途中の失敗で停止する。外側containerには`--device /dev/kvm`とネットワークを許可し、全体を同じ資源制限へ入れる。2つの試験diskとログのために追加で25 GiB程度の空きを用意する。以下の工具は個別実行にも使える。

`test-live.py --iso /build/live/<生成ISO> --output /build/test-bios --firmware bios`をビルダー内で実行する。`uefi`と`secure-boot`は別の新規出力ディレクトリで実行する。QEMUへ渡すのはISOと専用OVMF変数ファイルだけ。ホストdisk・HOME・bus・networkはゲストへ渡さない。`/dev/kvm`を使用できればKVM、それ以外はTCGで起動し、メモリ2048 MiB・1 vCPUに固定する。

KDE Liveの`--input-check`は、KWinのWaylandセッション上でKWriteを開き、Mozcを選択し、QEMUのキーボード入力から「日本語」へ変換して保存した内容を照合する。`--network-check`は任意の別試験で、QEMUの外向きuser networkingを有効にし、通常APT mirrorの索引を実際に検証・取得する。この場合は外側containerにもネットワークを許可する。ポート転送は作らず、ホストのディレクトリやbusは共有しない。

テストはシリアルからLiveへログインし、識別情報、systemd、dpkg整合性、コンポーネントの配置とread-only host observer、通常APT設定、Secure Bootを検査して電源を切る。選択デスクトップのプロセスを待ち、QMPで画面を保存する。成功markerはゲストで検査を通過した時だけ出す。`report.json`は実際のISO hashへ束縛する。デスクトップのプロセスと画面だけで、日本語入力・音声・GPU・実機の受入まで成功したとは扱わない。

`test-install.py --iso <ISO> --output <新規ディレクトリ> --firmware uefi`は新しい32 GiB sparse diskだけを作り、ネットワークなしでDebian InstallerのLive導入と、そのdiskからの再起動を試験する。`bios`も別に実行できる。ISOのインストーラーinitrdへ、試験用のpreseedを別ファイルとして追加する。元ISOと配布設定は変更しない。既存のlive-build preseedは保持する。`fixtures/install-vm.cfg`の公開試験パスワードは試験disk専用で、配布ISOに組み込まない。

インストール後は試験ユーザーでログインし、Liveユーザーが残らないこと、dpkg整合性、選択したAPT設定、デスクトップのログイン画面の稼働を確認する。既定のオフライン試験では「ネットワークミラーを使わない」を選択するため、Debian Installer標準のCDソースのみを期待する。通常のネットワーク更新先が設定されたと扱わない。

別の新規出力先で`test-install.py --network`を実行すると、`fixtures/install-network.cfg`でDebianの通常ミラーとsecurity・updatesを選び、再起動後に署名検証付きのAPT索引取得まで検査する。この試験では外側containerにもネットワークを許可する。インストーラーの標準HTTPミラーでもAPT署名検証を必須とし、LiveのHTTPSミラー検査とは区別する。

試験diskにはシリアルconsole用のGRUB設定を加える。実際の対話インストーラー操作や暗号化導入を試験したという意味ではない。各試験の`serial.log`、`qemu.log`、`report.json`と画面を保存する。試験diskもISOと同様にGitへ追加しない。

## 成果物と対応ソースの記録

ビルド完了後、ビルダーVM内で次を実行する。出力先は毎回新しくする。

```sh
sudo python3 /source/record-build.py --output /build/record
# Source collection only, after image building; the VM still uses the fixed snapshot.
sudo apt-get install -y --no-install-recommends devscripts liblwp-protocol-https-perl
sudo python3 /source/collect-sources.py --include-installer --output /build/corresponding-sources
sudo python3 /release/complete-sources.py --sources /build/corresponding-sources \
  --collector /source/collect-sources.py
```

`record-build.py`は実際のlive-build設定、コンポーネント入力、ビルダーの全パッケージ版、ISOと独自DEB/source packageのSHA-256を保存する。記録の生成自体を起動試験の成功にしない。独立した2回の完成ビルドを比較する場合は、`record-build.py --build /build-second --compare-with /build-first --output /build-second/record`を使う。入力manifest、ISOの集合・サイズ・SHA-256、実際の`cmp`を照合し、不一致なら`iso-comparison.json`へ失敗を記録して非0で終了する。比較結果を別マシンや異なる入力へ一般化しない。生成物にGit外のVM seedやSSH鍵を含めない。

`collect-sources.py`は保持したDEB/udebのSourceフィールドから正確なsource版を求め、同じ署名付きsnapshotからAPTで取得する。`Built-Using`と`Static-Built-Using`も対象とし、署名済みkernelの包みだけでなくLinux本体のsourceも保管する。epochやbinary NMUのsource版を保持し、独自パッケージは生成済み`.dsc`と完全なnative source tarを照合して保管する。途中で失敗した場合のreportは未完のままにする。`--resume`は同じビルド入力・同じ収集工具だけを受け付け、取得済みソースのhashを再照合して続ける。完成したLive package一覧の全バージョンが保存済みbinaryに対応することも検査し、欠落があれば停止する。対象はその一覧と保存したbinary/installer packageの集合であり、非自由firmwareのsource packageに可読なfirmwareソースがあると主張しない。大容量のソース取得分の空きを別途確保する。

`--include-installer`は通常・GUI両方のinitrd内のdpkg inventoryも読み、内蔵パッケージとインストーラーの構築元を追加する。現在のISOのudeb poolにない内蔵パッケージは、Debianの[debsnap](https://manpages.debian.org/trixie/devscripts/debsnap.1.en.html)で正確な過去版を取得し、そのcontrolフィールドからSource・Built-Usingを対応付ける。取得したbinaryを実行・インストールしない。固定APT索引に残っていない正確なsource版もdebsnapでHTTPS取得し、`.dsc`のSource/Versionと全アーカイブのSHA-256・サイズを照合する。この過去版の取得をAPTのアーカイブ署名検証済みとは表示しない。各source行へ取得方法を記録する。`--include-installer`なしのキャッシュ収集だけで、ISO内蔵インストーラーのソースまで網羅したと扱わない。

内蔵dpkg statusにはArchitectureが省略される。過去版binaryは`amd64`を指定し、その版が明示的に存在しない場合だけ`all`を取得する。debsnapへの複数architecture指定は両方の存在を要求するため、代替候補の指定には使わない。通信失敗を「パッケージなし」として処理しない。

最後に[署名用カーネルsourceの補完](../release/README.ja.md)も実行する。インストーラーudebで省略された本体への参照を、取得済みの署名用sourceの正式なcontrolから読み、不足する正確なLinux本体を追加する。元の収集reportは変更せず、`signed-kernel-sources/report.json`を別に保存する。配布物には両方のsource集合を含める。

一般ユーザーのホストへソース保管ディレクトリをコピーする場合、`rsync -a --no-owner --no-group`等でコピー先ユーザーの所有にする。VM内の`_apt`のUID/GIDをホストへ移す必要はない。`.dsc`・アーカイブ本体のバイト列は変えず、コピー後に両reportの全ファイルをサイズ・SHA-256で再照合する。

`make image-check`はビルドせずに工具の構文と境界条件を検査する。単独のdistribution repoとworkspaceの両方のCIに含め、同じMake targetへ委譲する。実ISOの生成・VM受入は上の手順で別に実行する。

workspaceには手動起動の`Debian 13 packages` workflowも置く。独自DEBを順にビルド・試験し、識別情報の復元を確認して、対応する独自source packageと一緒に成果物を保存する。GitHub上での実行結果とローカルでの実行結果は別に扱う。

ビルド入力が固定されていても、ISO全体のビット再現性は別の比較が必要。既存18実行ファイルの再現一致をISOの再現一致へ転記しない。`source=false`の開発ISOだけを一般公開しない。上流sourceの保管と公開用の署名・連絡先整備が必要である。
