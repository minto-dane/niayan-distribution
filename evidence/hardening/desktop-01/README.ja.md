# ハードニングの実VM受入

旧APT基準ISOのSHA-256は`d4c18dc0e2be653bf11a04db40db95ca0353322010133e068dda274bd4aa314b`。
追加したsysctl基準、Nia観測器のAppArmor profile、制限付きsystemd loaderを
実際のゲストに適用した。上流ソースと元のISO/導入済み試験ディスクは変更していない。

| 実行 | 結果 | 秒 |
| --- | --- | ---: |
| Live BIOS | PASS | 81.005 |
| Live UEFI | PASS | 85.578 |
| Live Secure Boot | PASS | 81.180 |
| 導入済みディスクの差分へ保存しSecure Bootで再起動 | PASS | 58.487 |

Live 3経路で全30項目の実行時基準、Nia hostctlの実観測、AppArmorによる機密読取・
ファイル作成・network・別プログラムexecの実拒否を確認した。実際のKDE Wayland、
Fcitx5/Mozc、KWriteで「日本語」を入力・保存し、非特権user namespace、DNS、
Firefoxのheadless起動とabout:blankの画像出力も確認した。BIOSの日本語入力画面を目視した。
Secure Boot時の`hostctl`出力には実SecureBootとkernel lockdownのSATISFIEDを記録した。
Live試験のfirmware引数と使用したOVMFのハッシュも保持する。

再起動試験は新規qcow2差分へ設定を保存し、正常な電源オフ後の2回目のSecure Bootで
loaderの自動起動、systemctlの失敗unit 0、全30項目、全入力ファイルのSHA-256を確認した。
元の試験ディスクは前後で同じSHA-256だった。強制電源断やNia transactionの試験ではない。

固定ツールimageのIDと外側3 GiB/swap 0/CPU1/pids128、ゲスト2 GiB/1 vCPU、
直列実行は`report.json`と各`runner.log`に記録する。最終4試験のVMは正常終了した。
`tools/`に使ったソース・設定を保持し、各レポートはそれぞれの入力hashに束縛する。

## 初期の失敗と修正

`attempts/01`はPTI設定名の版差と、Liveでenforce profileが無いことを検出してFAIL。
実際の6.12.107 kernel configの`CONFIG_MITIGATION_PAGE_TABLE_ISOLATION=y`を確認し、
検査名を対応するものへ修正した。AppArmorの有効フラグだけで成功へ変更していない。

`attempts/02`は新しいhostctl profileが`MC_Kernel_Read`のroot directory FDのopenを
拒否してFAIL。実ソースに従い`/ r,`だけを追加した。再帰読取や書込の許可は追加していない。
`attempts/03`は手動profileロード経路のPASS。その後、製品用の制限付きloader unitを
追加して最終の3経路と再起動を試験した。初期実行を最終構成の受入へ読み替えない。

Debian Liveの標準apparmor.serviceがoverlay条件でskipされる実ログを残す。
標準unitの条件を消さず、Niaの観測器用profileだけを専用unitで読み込む。

実機のGPU/無線/音声、性能の最悪値、全アプリの隔離、新ISO、Nia-onlyパッケージ管理、
強制電源断、更新・復旧は対象外であり未受入。新しいrootfs設定は製品統合待ち。
`manifest.json`は自身以外の全証跡ファイルをSHA-256へ束縛する。
