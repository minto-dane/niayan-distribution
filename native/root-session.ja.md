# 初回bank準備のcontroller session

0.6.0の`root_session.py`は、明示bootstrap済みの空の専用bankを初回root準備に使う内部controllerである。
root supervisorが実native admission・供給/世代認可・利用者同意を完了した後に呼ぶ管理面のRPCであり、
その判断自体を代行しない。稼働rootを切り替えるAPIや一般利用者向けの管理コマンドではない。

## 接続元と要求

`/run/niaos/root-session.sock`はroot:root 0600のAF_UNIX SOCK_SEQPACKETである。
SO_PEERCREDの接続元UID0/PIDに加え、各messageのSCM_CREDENTIALSを照合する。rootの接続FDを別processへ
渡しても、そのprocessのPIDでは観測を続けられない。SO_PEERPIDFDで接続元taskを保持し、書込許可前と
観測返却前に生存を確認する。未対応kernelでは拒否する。採用対象はDebian 13 amd64/Linux 6.12である。

ここで信頼する主体はroot管理面である。独立したsite署名や利用者consentの証明をRPC内で検証したとはしない。
root管理面を侵害したprocessや、root権限によるrecord/unit/raw-device改変への防御境界ではない。
本番の認可providerとnative SDKへのadapterは未接続で、通常導入時にsocketを有効化しない。

最初の正規JSON messageは、version=1、operation=prepare-freeze、既存Bank requestの全field、
独立期待worker SHA-256・device plan SHA-256・現在boot ID・bankのmount/device/inodeを含む。
保持archiveのO_RDONLY FDと、実native CAS lockのO_RDWR OFDをSCM_RIGHTSで添付する。
過大/非正規message、余分なfield/control、切り詰め、異なるFDや期限を拒否する。
CASのownerはrootではなく配備済みnia-pkgでなければならない。

## 準備と保持

1. 配備済みdevice/初期化記録と現在mountを再確認し、Bankの排他lockと選択block FDを保持する。
   bankのentryはbank.json/bank.lockだけを許し、初期状態がfilesystem単位でROであることを確認する。
2. `/var/lib/niaos/root-session.json`をO_EXCLで作成・fsyncし、要求・worker・device plan・bootを保存する。
   この初回使用barrierは、成功、失敗、切断、再起動でも自動削除しない。既存完了記録も上書きしない。
3. controllerだけがbankをRWへ変更する。別のPython childへ既存bank lock OFDとCAS/archive FDを渡し、
   setprivでcapability bounding/effectiveを従来worker用の7個へ制限する。CAP_SYS_ADMINとCAP_SETPCAPは
   childへ残さない。childは実capability mask、parent PID、worker pinを確認して元Bank.prepareを呼ぶ。
   setprivのparent-death signalと既存ELF workerのparent-death signalを使う。
4. child終了後にfilesystem全体をROへ戻す。FrozenRootで実identity/記録を保持し、別の権限縮小childで
   元workerの全archive再検査を実行する。正常結果だけを同じcontrollerの現在観測へ結び付ける。
5. 受信したCAS/archive FDのコピーを閉じてからfrozen応答を返す。supervisorは新しいnative CAS OFDを
   取得できるが、controllerのBank/device/root FDはsession終了まで残る。OFDへLOCK_UNは送らない。

以降のobserveはversion・stage・operationと新しいCAS/archive FDを必須とし、初回と同じscope、期限、
現在device plan/mount、元root/記録を再確認する。応答前に今回の受信FDを閉じる。毎回全treeを読み直すAPIではなく、
初回の全再検査と維持したfilesystem RO、現在のidentity/記録の確認を組み合わせる。
期限を延長・再認可せず、別stageへsessionを付け替えない。supervisor自身の予約・認可寿命も必要である。

## 終了と不確定結果

closeは同じversion/stageでFDなし。切断や期限切れもsessionを終了し、controllerはROを再確認して自分のFDを閉じる。
通常closeのEOFは、このcontrollerによるFD解放後に返す。外部supervisorのFDや別の特権writerの終了は保証しない。
`root-session-complete.json`のsession-endedは後片付けの記録であり、展開成功、公開、boot許可を意味しない。
展開中の切断・接続元終了は既発生の効果を取り消さない。childの期限と終了を待ち、現在性確認に失敗すれば成功を返さない。

SIGKILL/OOM等ではfinallyが動かない。systemdはKillMode=control-groupでchildを含めて停止し、独立の
ExecStopPostで元attemptに束縛したdeviceを再確認してROへ戻す。cgroup全体のSIGKILLはExecStopPostまで
巻き込むことがあるため、OnFailureは別cgroupのniaos-root-session-seal.serviceも起動する。このserviceは
SYS_ADMIN/DAC_OVERRIDE、128 MiB、swap0、CPU1、Tasks8でRO化だけを行う。busy/I/O失敗やplan変更で拒否した場合、
完了を捏造しない。電断でhookが動くとは主張せず、通常再起動は既存unitのRO mountと必須初期化検査を使う。
kernel I/O待ちの厳密な実時間上限は未保証である。再初期化、試行record削除、RWへの自動復帰は行わない。

初回使用recordができたbankでは旧root-preparation.serviceの再起動もassertionで拒否する。
controllerが保持中なら元Bank lockも第二writerを拒否する。既に元serviceが予約中ならcontroller側が拒否する。
完成済みrootを含むfilesystem全体を後の更新でRWに戻してはならない。bank slotの割当て・保持・GCと
更新用bankへの切替は次工程であり、本版は単一bankを再利用しない。

## 権限と検証

controllerは実mount namespaceで操作するため、namespaceを作るProtectSystem等を適用しない。
CAP_SYS_ADMIN/CAP_SETPCAPとchildへ渡す7 capability、AF_UNIX、namespace作成禁止、NoNewPrivileges、
1 GiB/swap0/CPU1/Tasks32/FD64/dump禁止で制限する。元準備serviceのcapability/device viewは拡大しない。
新childはtarをparseする前に既存ELF workerのchroot/FD閉鎖/seccompへ入る。controllerのhost mount権限を
tar parserへ渡さない。controller自身の侵害を封じる完全なsandboxとは表現しない。

`worker/check_root_session.py`は使い捨てVMの明示専用partitionと実配布packageを使用する。
非root接続、誤worker/mount/device plan/FD、実worker準備・再検査、CASの再取得とBank保持、observe/close、
切断・期限切れ・controller強制終了を検査する。強制終了caseは保持中に試験だけでRWへ変え、stop hookのRO復帰を確認する。
全tree/元記録の不変、使用済みbank拒否、通常caseの再起動後ROと旧writer拒否も確認する。
人工requestとarchiveはsite認可ではなく、native SDK全世代処理や書込中の物理電断を受入したことにはしない。

根拠: [Debian 13 setpriv](https://manpages.debian.org/trixie/util-linux/setpriv.1.en.html)、
[UNIX domain socket](https://manpages.debian.org/trixie/manpages/unix.7.en.html)、
[LinuxのSO_PEERPIDFD定義](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/socket.h)。
