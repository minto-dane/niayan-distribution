# 検証起動・Trial・モジュール署名

2026-09-12の製品必須条件。現行の独自管理器/boot executorは未接続であり、この仕様や
純粋Adaモデルのコンパイルを、実起動・TPM・署名・NVIDIAの受入へ読み替えない。

## 起動チェーン

インストーラー起動→インストール→初回起動→通常更新→Trial→rescueまでSecure Bootを
有効にしたまま使う。Microsoft署名済みの上流shimを改変せず使い、現在のfirmware db/dbx、
shimのSBATとMOK/MOKXも確認する。鍵の手動登録が必要な構成でもSecure Bootを無効化せず、
信頼されたMokManagerで本人が指紋を確認する。自動登録や検証無効化を成功条件にしない。

Debian 13の署名済みshim/GRUB/kernelを使った既存ISOには導入/再起動のVM受入がある。
これはkernelまでのSecure Boot受入であり、可変initramfs、コマンドライン、root全体までの
Verified Bootではない。新しい本番構成では、使用前に認証されたkernel/initrd/cmdlineと
root hash、dm-verityで読むOS内容、実行に影響する設定・モジュール・追加イメージを一つの
許可された世代へ固定する。測定/PCR値をログへ保存するだけでは実行の禁止にならない。

上流systemd-stub/ukifyによる署名UKIは候補であるが、Debianのkernel署名は独自UKIの外側を
署名しない。任意の製品鍵をDebian shimが最初から信頼すると仮定しない。最初のインストーラー
から完全な検証を行うには、製品UKIまで既に信頼がつながる配布署名、またはSecure Bootを
維持した明示的な事前鍵登録が必要。Microsoft署名取得・製品鍵の実運用は未完で、私有鍵や
試験鍵をrepository/ISOへ同梱して穴を埋めない。対応firmwareのCA世代も配布対象へ含める。

UKIの外部addon、profile切替、追加initrd/credentials/confext/sysext、ESP上の設定や順序を
すべて検査対象にする。「署名済みaddonなら何でも可」は認めない。インストーラー/rescueも
同じ署名・下限の対象とし、別ESP、removable fallback、古い署名付き媒体、kexec、休止復帰を
検証迂回路にしない。mutable業務データはOS用verity領域とは分離し、OSコードへのwrite overlayで
検証を無効にしない。既存のmutable-root研究profileは本番検証起動構成ではない。

## 明示的な世代切替と復旧

Trialは必須ではなく、自動Trial・失敗回数による旧版復帰を標準経路から外す。
待機側で準備し、保守計画、業務データ互換、独立復旧手段、必要ならquorum/余力/fencingを確認して
明示的に切り替える。切替後の健全性監視は残すが、その失敗を旧版起動の許可に変換しない。
逆方向へ戻す操作も、現在の方針・データ・原本・認可を伴う新しい管理トランザクションにする。
商用OSの待機インスタンス保守、共存条件付き逐次再起動、一時適用/確定の役割分離を参考にした
niayanの設計判断である。単に同じ名称のコマンドを用意することを同じ保証と見なさない。

`statecore/src/state_boot.*`は鍵の信頼epochとは別にSecurity_Versionを持つ。
これは署名された完全なboot bundleの既知の禁止下限で、DEB版番号や「脆弱性がない証明」ではない。
署名/失効/データ互換/完全な検証起動がすべて必要で、同じ鍵で署名された版も下限未満なら拒否する。
下限以上であっても自動的な旧版復帰は許可しない。新しい版にも未知の脆弱性や回帰はあり得る。

新しい切替の前に、その下限を満たすrescueを独立に準備する。新しい正確な方針認可の下で
Prepare_Activationが下限を引き上げ、一回の起動権を用意する。方針、node、全候補、起動権、
世代をhashへ固定し、現在の独立した非rollback anchorとの一致を求める。
署名だけの古い台帳、root所有file、ESPのfilename counter、VM/disk snapshot、時計、可変UEFI変数を
非rollback anchorの代用にしない。TPM NV等の実provider・更新権限・電断回復・消耗対策は未実装で、
現行の独自モデルはanchorがなければ通常候補を選択しない。

Consume_Activationの永続化/anchor更新/独立readback後に、元の選択済み候補へ制御を渡す。
消費後にChooseを呼び直してその一回を飛ばさない。実行前の停止でも起動権を自動で戻さない。
未確定の切替後は、同じ下限を満たす旧世代であっても自動選択せず、検証済み限定rescueを選ぶ。
該当候補がなければRecovery_Onlyとなり、いずれのcandidateも起動許可しない。
rescueでは通常の秘密情報を解放せず、業務データを自動的に書換えず、anchorを初期化しない。
Complete_Activationは同じnode/policy/imageとfreshな複数健康観測、正確な終端認可を必要とし、
確定した世代だけを次回以降の通常起動先とする。新stateのanchor更新/readbackも引き続き必須。

`State_Boot_Assessment`は整合性違反をHeldに固定する。ネットワーク/クラスタ再参加、監査の
一時的不調など、整合性を満たした状態での健全性不足は安定期間を再評価し、旧版起動・再起動・
起動権リセットの許可にしない。認証済み健康observerも外部DoSの影響を受ける。
遠隔の応答だけを起動成功の必須条件にせず、ローカルの必須整合性と外部サービス利用可否を分ける。
GUI/GPUだけが失敗した場合の復旧も、未署名ドライバー許可やSecure Boot無効化にしない。

Linuxの公表文書は、修正時点ではsecurity影響が明らかでないbugがあることを明記している。
CVE/勧告の不在、件数、公開日だけでkernelを安全と判定しない。`State_Kernel_Supply`は、保守対象の
stable修正集合とDebianの正確なbackport/coverage対応のfreshな認証済み観測を要求する。
`State_Kernel_Maintenance`と`State_Kernel_Health`はこれが欠けると判定保留/Unknownを返す。
公開済み修正を追跡していることと、全修正の適用済み/欠陥の不在は異なる。実feed/providerは未接続。
Debian 13の上流パッチ無改変方針を維持し、mainlineへ無条件に乗り換えず保守対象の更新を追う。

継続的な電源妨害や資源占有に対する可用性は、暗号やTrial撤去だけでは保証できない。
CPU/memory/IOの予約、隔離した診断領域、ローカル操作、独立rescue、クラスタの余力と運用対応を
組み合わせる。下限を守った結果の停止を、古い版の無条件起動で隠さない。
下限更新前後の電断、anchor喪失/再作成、失効後のrescue、インストーラーによるtrust領域の
再初期化、DB schema不可逆変更、鍵更新途中、全node同時更新もリリース前障害試験の対象とする。

## NVIDIA・MOK

標準のDebian NVIDIA供給をnative catalogへ取り込み、GPU/ドライバー種別/正確なkernel ABI、
firmwareとユーザー空間の版を一つの計画へ固定する。`.run`等の別管理主体や稼働root上の任意ビルドへ
逃がさない。DKMSは隔離されたビルド工具として使い、署名は認証済み原本と出力digestを限定した別境界で行う。

`module_identity.py`は内部のオフライン鍵準備工具である。RSA 3072/SHA256、CA=false、署名のみの
KeyUsageとmodule-only EKUを持つ1年の自己署名証明書、暗号化PKCS8を新しい私有directoryへ作る。
秘密のpasswordは専用FDから受け、平文私有鍵を保存しない。証明書指紋と未登録状態をmanifestへ記録し、
途中出力を上書きしない。鍵生成自体はランダムで、配布OSの再現ビルド入力とは分離する。
現段階では工具の構文コンパイルのみで、実鍵生成・MOK登録・driver build/sign/loadは未受入。

module-only EKU `1.3.6.1.4.1.2312.16.1.2`を持つMOKはshimのEFIイメージ検証では拒否される。
boot/UKI用の鍵と分け、通常の汎用MOKを「ドライバー専用」と表示しない。ただしmodule-only鍵は
任意のkernel moduleを署名できるため、漏洩するとkernel制御につながる。暗号化保存だけで実行中の
署名oracleを保護したとはしない。隔離signer、限定されたnative計画認可、署名出力の独立照合が必要。

実製品のMOK登録要求は指紋の確認→MokManager→次回起動での実登録・kernel trust観測まで
pendingとして扱う。登録拒否/中断をdriver使用可能としない。更新時は新kernel用の署名済みmodulesを
initrd/rootの検証対象へ組み込んでから明示的に世代を切り替える。鍵の更新/失効時は全boot/rescue候補との
互換を確認し、古いroot復元でMOKXや失効台帳を戻さない。実signer・enrollmentとGPU試験は残件。

## 参照した上流仕様

- [Debian Secure Boot](https://wiki.debian.org/SecureBoot)、[CA移行](https://wiki.debian.org/SecureBoot/CAChanges)、[Trixie shim-signed](https://packages.debian.org/trixie/shim-signed)
- [systemd Automatic Boot Assessment](https://github.com/systemd/systemd/blob/main/docs/AUTOMATIC_BOOT_ASSESSMENT.md)、[systemd-stub v257](https://raw.githubusercontent.com/systemd/systemd/v257/man/systemd-stub.xml)
- [Linux CVE方針](https://www.kernel.org/doc/html/next/process/cve.html)、[stable保守](https://www.kernel.org/doc/html/latest/process/stable-kernel-rules.html)
- [Linux dm-verity](https://www.kernel.org/doc/html/latest/admin-guide/device-mapper/verity.html)、[module signing](https://www.kernel.org/doc/html/latest/admin-guide/module-signing.html)
- [shim 16.1 verify_eku](https://raw.githubusercontent.com/rhboot/shim/16.1/verify.c)、[NVIDIA module種類](https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/kernel-modules.html)、[Debian NVIDIA](https://wiki.debian.org/NvidiaGraphicsDrivers)

参照日は2026-09-12。上記から導いたniayanの設計条件と、上流が実装している機能を区別する。
