# 非特権世代からroot supervisorへの準備要求

内部SDKのみ。public listener/launcherや本番supervisorを配備するものではない。
`Pkg_Generation_Stage.Prepare_Root_Using`は必須transportの前後で元の認可・内容・設定を照合し、
実stage/root/CAS予約を保持する。旧`Prepare_Root`も同じ共通処理を利用する。

`Pkg_Root_Handoff`はrootが起動前に作成したAF_UNIX/SOCK_SEQPACKET pairの子側FDを借用する。
両端で起動前にSO_PASSCREDを有効にする。C側はroot peerのSO_PEERCREDとSO_PEERPIDFDを保持し、
各応答のUID/PIDを照合する。root側Channelは実起動から得たdirect child PIDと期待UIDを使う。
pidfdとwaitid(WNOWAIT)でlive/unreapedな実子を要求し、各要求のPID/UIDを照合する。
client本文のUID/PIDやPIDだけへのfallbackは使わない。

rootは独立に採用したScopeを渡す。受信messageからScopeを作って期待値にしてはならない。
このtransportはoperator認証、供給、計画同意、世代admissionを自動的に行わない。

## 正規wire

要求は192 byte固定。整数はunsigned big-endian、digestとidentityは生bytes。

| byte offset | 長さ | 内容 |
|---|---:|---|
| 0 | 8 | ASCII NIAHND01 |
| 8 / 40 / 72 / 104 | 各32 | generation / root manifest / archive / worker |
| 136 | 16 | stage |
| 152 / 160 / 168 | 各8 | archive size / entries / 元boottime期限ms |
| 176 | 16 | すべてzero |

identityはzeroを拒否する。sizeは1024から8 GiBまで、512 byteの倍数。entriesは1から524288まで。
期限は正のsigned64範囲でOpen時から最大600秒。送信時に同じ元期限を要求し、更新しない。
実archive FDと実native CAS reservation FDをSCM_RIGHTSで二つだけ渡す。
root controllerは引き続きFDの実体・OFD・原本・device/worker等を照合する必要がある。

応答はASCII NIAHOK01と元要求全192 byteのSHA-256の計40 byte。準備完了だけを意味し、
公開・起動・同意・独立inode観測の証拠ではない。余分なbyte/FD/control、異なるhash/送信者を拒否する。

## 寿命と異常

C Sessionとroot Channelはそれぞれ一度の準備要求に限る。送信試行後は再試行せず、不明な結果をIndeterminateとする。
rootのreceive失敗後は再受信できず、complete失敗後は再送できない。別channelを用いた再試行の可否は
native履歴・永続attempt・新しい認可で判断する別問題で、このSDKだけで全体の重複実行を防止したとはしない。

rootの呼出側はroot session準備、独立root観測、現在認可の再照合を終えてからcompleteを呼ぶ。
completeは受信FDコピーを閉じてから応答する。取消packet、切断、子の終了、期限切れを拒否する。
その後の全寿命監視、取消による資源遮断とcontroller終了は呼出側の責務で、背景監視を実装したものではない。
borrowed channelの所有者は物理排他の全寿命を保持し、SDK Close/Finalizeをremote cleanup完了として扱わない。

再検査handoff、本番launcher、現在供給/世代admission、正確な同意、root controllerへの製品接続は未完。
新C基準への全transport適合と形式検証も未完であり、純粋wire検査の証明だけでは本番受入しない。
ADR-0117/0118とimplementation-assurance.ja.mdに従う。
