# Debian 13デスクトップのハードニング基準

NiaOSの設定・成果物・実行時状態を同じ基準で検査する。2026-09-08に公式資料を
確認した。新規設定の正本は`baseline.json`、標準sysctl断片は`rootfs/`に置く。
既存のAPT版ISOへ恒久組込みしたものではなく、Nia-only rootへの統合待ちである。

Ubuntuの[メモリ保護](https://documentation.ubuntu.com/security/security-features/process-memory/)と
[コンパイラ保護](https://documentation.ubuntu.com/security/security-features/process-memory/compiler-flags/)を
参照し、ASLR、PIE、実行不可スタック、RELRO、即時シンボル解決を確認する。
既存Nia GPRにはPIE、`-fstack-protector-strong`、RELRO/NOW/noexecstackがある。
ELF検査は実成果物のprogram header/dynamic flagを読み、対象プログラムや`ldd`を
実行しない。canaryやすべてのコンパイラ変換の存在をELF検査だけで証明しない。

ANSSIの[GNU/Linux構成勧告 v2.0](https://messervices.cyber.gouv.fr/documents-guides/linux_configuration-en-v2.pdf)
（特に動的kernel設定、ファイルシステム、静的kernel設定）を参考にする。
同勧告もモジュールの全面禁止や独自kernelの維持費に注意している。
私たちの一般デスクトップ用途では、設定数を最大化することを目的にしない。
独自kernelを保守する経路を増やさず、Debian kernelに備わる保護を検査する。

Kicksecureの[security-misc](https://www.kicksecure.com/wiki/Security-misc)は、
任意設定の互換性を確認することや、ハードウェア情報隠蔽が表示サーバーの起動を
妨げる場合があることを明記している。私たちは全設定をコピーせず、個別の境界を採用する。

## 採用値と互換性

sysctlの意味は[Linux kernel文書](https://docs.kernel.org/admin-guide/sysctl/kernel.html)と
[ファイルシステム設定文書](https://docs.kernel.org/admin-guide/sysctl/fs.html)で確認する。

| 設定 | 既定値 | 理由と制約 |
| --- | ---: | --- |
| `kernel.randomize_va_space` | 2 | heapを含むASLR |
| `kernel.kptr_restrict` | 1 | 非特権へのkernel pointer露出を制限。管理者の診断を維持 |
| `kernel.dmesg_restrict` | 1 | kernelログには管理者権限を要求 |
| `kernel.unprivileged_bpf_disabled` | 2 | 非特権BPFを制限。値1の再起動まで不可逆な制限は追加しない |
| `vm.unprivileged_userfaultfd` | 0 | kernel fault処理の権限を制限。全userfaultfd機能の削除ではない |
| `vm.mmap_min_addr` | 65536 | 低位アドレスのmappingを制限 |
| `fs.protected_hardlinks` / `symlinks` | 1 / 1 | 他ユーザーのファイルを使うlink攻撃の緩和 |
| `fs.protected_fifos` / `regular` | 1 / 2 | sticky directory内の他ユーザー所有オブジェクトへの意図しない書込を制限 |

userfaultfdの範囲は[公式文書](https://docs.kernel.org/admin-guide/mm/userfaultfd.html)を参照。
設定の多くはDebianですでに有効であり、確認した既定値を新しい発明と数えない。
`audit.py`は一部のより強い値も受け入れる。VM適用試験は、すでに受入範囲内の
強い値を弱い値で上書きする場合は設定前に拒否する。
本番の生成時も既存の管理者設定をconfigcoreで保持し、固定断片による格下げを避ける必要がある。

user namespace、IPv6、USB、32-bit ABI、JIT、hibernate、SysRqは一括禁止しない。
ptraceの全面禁止、`/tmp`の一律noexec、panic強制、全モジュール禁止、全プロセスの
`MemoryDenyWriteExecute`、allocatorの全体LD_PRELOADはこの基準に含めない。
必要なサービス隔離は、そのサービスの実アクセスと復旧経路を試験して個別に追加する。

`nia-hostctl` AppArmor profileは、既存の読み取り専用観測器だけを対象にする。
`State_Host_Probe`、`MC_Kernel_Read`、`MC_Clock`の実入力を読み取り許可へ列挙し、
管理対象への書込、機密ファイルの読取、ネットワーク、別プログラムの起動を与えない。
[DebianのAppArmor仕様](https://manpages.debian.org/trixie/apparmor/apparmor.d.5.en.html)の
標準profile/attachmentを使い、上流やAdaソースの改変は不要である。
この観測器の制限を、未接続のpkg workerや全デスクトップの隔離と同一視しない。

## 検査

```sh
make hardening-check
python3 hardening/audit.py --render-sysctl
python3 hardening/audit.py --elf /path/to/nia /path/to/hostctl
# NiaOSの専用試験VM内で実行。読み取りのみ。
sudo python3 hardening/audit.py --runtime
```

無いsysctl、読めないkernel config、AppArmor profile観測不可を成功扱いしない。
AppArmorが有効でenforce profileが一つ以上あることは、全アプリの閉じ込めを意味しない。
kernel configの有効値と一部の保護を無効にする起動引数も調べる。CPU固有の
全脆弱性やハードウェア保護を網羅する検査ではない。

`test_vm.py`は固定ツールコンテナ・外側3 GiB/CPU1/pids128の制限内で1件ずつ実行する。
ゲストは2 GiB/1 vCPU、ISOは読み取り専用、設定変更はLiveのRAM内だけである。
rootで設定を適用・再読し、実際のKDE Wayland/Fcitx5/Mozcで「日本語」を入力して
KWriteへ保存、非特権user namespace、DNS、Firefoxのheadless起動を試験する。
ネットワーク試験にはコンテナにも外向き通信が必要である。

```sh
python3 hardening/test_vm.py --iso /artifacts/niaos.iso \
  --output /new-output/hardening-bios --firmware bios
```

ツール・設定・ISOのhashをレポートへ束縛する。この試験は変更後のISO構築、
起動早期の設定適用、設定の永続化、実GPU/音声/無線、省電力、性能の受入を代替しない。
「全ユーザーの使用感に影響なし」やUbuntu/Kicksecureより安全という比較を未測定で宣言しない。
