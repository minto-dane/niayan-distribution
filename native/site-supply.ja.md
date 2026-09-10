# 独立したsite供給provider

`Pkg_Site_Supply`は世代公開のObserve_Supplyへ渡す、非特権の実providerである。
CASに保存したpolicyやreceiptから鍵・epoch下限・時刻を取り出して自己承認しない。
rootが管理する現在policyと別の下限記録を読み、現在UTCをOSから採取する。
CASを再予約しないため、公開側が実CAS予約を保持している間にも呼び出せる。
共有API、元DEB、NIAGEN05/NIASPOL1のbytesは変更しない。

## 保護入力と配備契約

推奨配置はpolicy directory `/etc/niaos/supply` と、世代rootのrollback対象から分離する
floor directory `/var/lib/niaos/trust`。それぞれの `supply.bin` と `supply.floor` を読む。
全祖先directoryはroot所有・group/other書込不可、symlinkなしを必須とする。
fileはroot所有の単一link通常fileで、modeは0440/0640/0444/0644のみ。
鍵は公開鍵であり、0640を使う場合は専用core accountに読取groupを付与する。
UID0でのprovider実行、core自身が所有するpolicy、writable祖先、欠損や形式不明を拒否する。

この実装はroot管理者が明示配備したfileを信頼する境界であり、fileのhash自体は署名ではない。
配布物に本番鍵・空の既定policy・同意なしの自動生成/書込を含めない。
installerは署名/認可済みの運用policyからこれらを配備し、floor保管先を世代切替から分離する必要がある。
現在はその全installerとhardware/外部anchorによるrollback耐性の受入が未完である。

## wire形式

整数はunsigned64 big endian、意味上は1〜2^53−1。全sizeは厳密で、余剰・省略・未知版を拒否する。
policyは以下の56-byte headerに、厳密なscope昇順のauthority行を0〜256個続ける。

|0起点offset|bytes|内容|
|---|---|---|
|0|8|NIATRST1|
|8|16|対象root identity、zero不可|
|24|8|policy serial|
|32|8|not-before UTC秒|
|40|8|exclusive expires UTC秒|
|48|8|authority件数、0〜256|
|56以降|各80|scope32、Ed25519公開鍵32、security epoch下限8、最大経過秒8|

scope/keyはzero不可、scope重複や逆順を拒否する。最大経過秒は1〜3600。
empty policyは表現できるが、非空の供給を認証したことにはならず、実公開側の完全一致検査を省略しない。

floorは72 bytesで、NIAFLOR1(8)、root identity(16)、minimum policy serial(8)、
minimum UTC(8)、完全なsupply.binのSHA-256(32)。scopeごとのepoch下限とは別の、
運用policyそのものの版・時刻下限である。floor自身をCASやreceiptから作ってはならない。
policy serialが下限未満、rootが不一致、完全hashが不一致なら拒否する。

## 公開処理との接続

計画作成前は[供給planner](supply-planner.ja.md)の`Open_Planning`/`Observe_Planning`を使う。
架空のplan/map/policyを渡さず、完成後に同じtrust pinを保持する`Bind_Publication`で束縛する。
計画用sessionは公開用Observeを満たさない。

Openはpolicy/floor directoryと、root/transaction/physical plan/retained policy/mapの正確な
context、finite BOOTTIME deadlineを受ける。contextは呼出側のassertionであり、それだけで
公開を認可しない。初回観測で独立policy/floorをpinし、Observeは毎回保護fileを読み直して
FDとpathのinode/属性、完全hash、serial、時刻範囲を再確認する。
`Observe_Current`はcontextをgenericに束縛し、既存publisherのcallbackと同じsignatureになる。

providerが返すMapは束縛されたcontext、Trustedは保護policy、Observed_Atは独立採取した現在UTC。
公開側は既存通り、実root.state/manifest/retained policy/map、全署名記録、元DEB/control、
現在の鍵/epoch/ageを同じwriter/CAS予約の下で完全照合する。
このproviderは効果契約、停止barrier、同意、health、世代認可の代わりにはならない。

各観測の失敗では全出力を消し、sessionを閉じる。policy/floor変更を処理途中で自動採用せず、
明示的な新しいOpenが必要である。実処理の失敗を未実行と推定せず、publisherの既存journal/
復旧判断へ渡す。policy更新時は管理要求を休止し、設定と下限を耐久配備してから明示再開する。

UTCはfileの時刻ではなくOSのCLOCK_REALTIMEから読む。floor、not-before、expiresに加えて、
呼出し内の逆行とsessionのhigh-water markを確認する。I/O deadlineはCLOCK_BOOTTIMEで前後確認する。
OSの時計を変更しない。正しい時計の確立、volumeごとrollbackされたfloorへの対策、
同期I/Oも含む厳密な実時間制限は信頼されたsite/supervisorの責務として残る。

## 内部配備確認

`pkg_supply_observe`はcomponent DEBの `/usr/libexec/nia/` にだけ配置する読取専用工具である。
二つのdirectory、root/transaction identity、plan/retained policy/map hashの七引数を受け、
5秒のBOOTTIME deadlineでOpen/Observeを行う。出力はversion付き固定機械形式で、
公開管理UI側が必要な翻訳を行う。成功にもexecution_permit=falseを出力する。
公開の別管理コマンド、世代更新入口、署名発行サービスではない。

## 検証と残る範囲

新しいAda mainの形式/境界検査、既存publisher回帰、使い捨てVMでの実root-owned入力/
原子的policy更新/欠損/不一致と、実publisher callback接続を確認する。
VMの署名鍵とmanaged/barrier/health/effect認可は明示fixtureであり、本番配備しない。
本番署名observerと秘密鍵保管、全managed/世代認可adapter、installerによるpolicy/非rollback
floorの配備と時刻確立、全DEB効果、実boot切替/復旧と完全置換ISOは引き続き未完である。
