# 非特権世代からroot supervisorへの準備・再検査要求

内部SDKのみ。public listener/launcherや本番supervisorを配備するものではない。
`Pkg_Generation_Stage.Prepare_Root`は必須transportの前後で元の認可・内容・設定を照合し、
実stage/root/CAS予約を保持する。準備・再検査は明示的なtransportを必須とし、SDKに旧socket直結入口やUsing別名を残さない。

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

C Sessionとroot Channelはそれぞれ一度の準備または再検査要求に限る。送信試行後は再試行せず、不明な結果をIndeterminateとする。
rootのreceive失敗後は再受信できず、complete失敗後は再送できない。別channelを用いた再試行の可否は
native履歴・永続attempt・新しい認可で判断する別問題で、このSDKだけで全体の重複実行を防止したとはしない。

rootの呼出側はroot session準備、独立root観測、現在認可の再照合を終えてからcompleteを呼ぶ。
completeは受信FDコピーを閉じてから応答する。取消packet、切断、子の終了、期限切れを拒否する。
その後の全寿命監視、取消による資源遮断とcontroller終了は呼出側の責務で、背景監視を実装したものではない。
borrowed channelの所有者は物理排他の全寿命を保持し、SDK Close/Finalizeをremote cleanup完了として扱わない。

再検査handoffの要求/応答を追加した。本番launcher、現在供給/世代admission、正確な同意、root controllerへの製品接続は未完。
新C基準への全transport適合と形式検証も未完であり、純粋wire検査の証明だけでは本番受入しない。
ADR-0117/0118とimplementation-assurance.ja.mdに従う。

## root Channelの制御と解放

ADR-0119によりroot側は明示的な有限状態を使う。受信・応答の試行はI/Oの前に記録し、
失敗はFAILED、closeはCLOSEDへ移す。どちらからも受信や応答を再開しない。
closeは所有参照を先に取り外し、FDのOSErrorでも残りの入力FDとpidfd/socketの解放を試みる。
Linuxのclose失敗を同じFD番号への再試行で補わない。入力の解放エラーは成功応答を禁止する。
元期限を維持し、waitは最大1200 poll呼出しでも終了する。

`make handoff-check`はroot_handoff.pyとcheck_handoff_lifecycle.pyの厳格型検査と、
実transition関数の全到達制御状態の検査を行う。独立履歴の順序/回数/終端性を検査し、
探索深さで省略しない。モデルと実際のI/O経路との対応は状態変更位置と境界試験で確認する。
これは全Python/OS/FD実装の形式証明ではなく、製品の本番認定を与えない。

再検査も`Reinspect_Root_And_Hold`の必須transportへ実archive/CAS FDを渡す。
`Observe_Root`は前後の独立観測として別に必要で、元期限と物理identityの不一致を拒否する。
跨UID protocolは以下のReinspectで接続できる。これは保持root sessionを接続可能にするSDK境界であり、
本番の認可/同意providerと全寿命supervisorの完成ではない。
旧service/RPCは廃止した。共有Bankと必要な試験は保持sessionの経路へ移す。
撤去判断・ACID境界・オフライン更新条件はassuranceのADR-0120に記録する。

## 再検査要求

`Pkg_Root_Handoff.Reinspect`は別のprivate channelを使い、既に保持しているrootの再検査を要求する。
起動時に用意したFDを借用し、root側は独立に導いた`ReinspectionScope`をChannelへ渡す。
準備channelを再利用せず、元のcontroller sessionと物理排他は保持し続ける。
再検査の失敗を新規展開に切り替えたり、別channelで自動再試行したりしない。

要求は224 byte固定。offset 8〜175は準備と同じ構成で、168は今回の交換期限である。

| byte offset | 長さ | 内容 |
|---|---:|---|
| 0 | 8 | ASCII NIAHRV01 |
| 176 | 8 | 元の展開期限 |
| 184 / 192 | 各8 | 独立に期待するmount ID / inode |
| 200 / 204 | 各4 | device major / minor |
| 208 | 16 | すべてzero |

元期限は正のsigned64、mount/inodeはzeroでないunsigned64、deviceはunsigned32。
wire上の元期限は保存値への束縛であり、それを根拠に失効したcontroller sessionを復活させない。
応答はNIAHRK01と全224 byteのSHA-256。準備用の応答はhashが正しくても再検査成功にはならない。
native側では有効な要求の送信試行によりSessionが消費され、以後どちらの操作もConflictとなる。

supervisorは同じ保持controllerのObserve、独立root観測、現在の供給/認可/同意を確認してから
completeする。受信した期待値を独立観測の代わりにせず、受信FDのコピー解放を応答より先に行う。
新しいwire validatorと準備validatorの形式証明は288 propertyを通過した。範囲は純粋な形式検査と
メモリ境界のみ。実Ada/C/Pythonの32通信caseで送信者/FD/期限/取消/再送/対象不一致を検査した。
OS全体・全C transportの証明、実物理再検査と本番認可を含む一貫した経路の受入は別に必要である。
