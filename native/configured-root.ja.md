# 設定済みrootと保持記録

`Pkg_Configured_Root.Build`は元NIAROOT1/2、catalog/closure、root/transaction/context、
architecture、live設定選択から、完全なtar、生成manifest、全参照の保持記録を同じCASへ保存する。
判断ADR-0105。公開コマンド・第二のDB・pinや実行許可は追加しない。

## 構築

1. Pkg_Root_Configuration.Prepareで元所有権・全宣言・最終path・全選択を再検証する。
2. 元catalogから各base claimの原本tar位置を再観測する。設定はPkg_Configuration_Entryへ渡す。
3. rootと全directoryをraw path順に先行させる。その他のbaseは原本順とhardlink依存を維持し、
   設定entryを最終path順で続ける。設定対象を横切るhardlinkは既存配置検査でUnsupportedとなる。
4. 未変更の元header/拡張/body/paddingをそのままコピーする。設定はprefix、正確なcontent、
   512 byte境界までのzero paddingを出し、全体の終端へ1024 zero byteを加える。
5. 64 KiB bufferによる二回のstreamでhash計算とCAS保存を行う。内容を全体bufferへ読み込まない。
   各sourceをhash検証して開き、同一sourceのstat変化も確認する。全出力サイズにheader/paddingを含める。
6. manifestとexactな保持集合を保存する。返却前に全選択をlive再確認し、期限・変更・欠損を拒否する。

元の閉包は全memberの存在確認を済ませたうえで読み、読み終えたbyteのhashとstatも再確認する。
新しい保持記録は、catalogと各選択の既存閉包memberの和集合に、元manifest/archive、選択記録、
生成prefix/content、生成manifest/archive、各閉包自体を加えたstrict sorted unique集合である。
削除した設定の選択、旧vendor原本、ローカル観測、退避内容も参照集合に残る。

## NIACRT01

整数はbig-endian。固定headerは320 byte。

| 0始まりoffset | 内容 |
| --- | --- |
| 0 | tag 8 byte |
| 8, 40, 72 | 元manifest、catalog、catalog closureのdigest各32 byte |
| 104, 136 | 元archive、所有権bindingのdigest各32 byte |
| 168, 184 | root ID、transaction ID各16 byte |
| 200, 232 | context、architectureのraw byte列のSHA256各32 byte |
| 264 | 生成tarのdigest 32 byte |
| 296, 304 | tar全長、最終entry数各u64 |
| 312, 316 | choice数、生成設定entry数各u32 |

続くchoice数×96 byteは、入力順のproposal/decision/closure各digestである。
さらに生成設定entry数×80 byteを最終path順で並べる。
各rowは最終配置の1始まり位置u64、prefix digest、content digest、content size u64。
元claim選択は元manifestへ束縛する。出力の識別に必要な元属性/変更内容は選択と原本に残す。

## NIACRC01

固定headerは48 byte。tag 8 byte、生成manifest digest 32 byte、member数u64に続き、
strict ascendingなmember digest各32 byteを並べる。この保持記録自体はself-referenceを持たない。
最大集合は既存catalog閉包上限+40×最大choice数+8に制限する。

`Verify`は期待manifest/保持記録と元Build引数・live選択を要求する。
先に以下の保存参照loaderを実行し、その後にlive配置と選択を再検証するBuildのmanifest/保持digestを比較する。
正しい保存閉包が指す欠損を、検証中に原本から再生成して成功扱いしない。
再構築が必要ならcallerが別のBuildを明示的に行う。旧記録を書き換える復旧APIではない。

## 保存参照の読込み

`Pkg_Configured_Root_Record.Load`は再起動後にもlive proposalなしでNIACRT01/NIACRC01を読む。
判断ADR-0106。全保持object、記録のhash/stat、元root/catalogと選択のscope、長さ・順序・サイズ、
宣言されたcatalog/choice閉包と生成物の和集合を検査する。CASを書かず、欠損を再生成しない。
成功したViewから元binding/architecture/出力、全選択、設定entry、保持memberを列挙できる。
削除でfileを残さない選択も含む。失敗は以前のViewを消し、未検証の部分結果を返さない。

最大manifestは1,048,896 byteであり、1 MiB固定bufferに制限しない。
member列挙はNIACRC01の中身で、NIACRC01自身は含まない。後段の保持rootでは両者が必要である。
新しい有限期限は読込にだけ適用する。旧proposalの期限は履歴で、実行期限として更新しない。

このLoadは参照整合性の検査である。宣言閉包の原本からの完全性、所有権・配置・設定効果の意味、
現在のroot状態や認証を検証したものではない。期待digestと返却scopeを後段で認証し、
実行時には従来のlive Verifyと本番admissionが必要になる。単独でGC・復旧適用の許可に使わない。

## 実行境界

世代engineがCAS予約を開き直した場合は`Verify_Current`で現在のroot FDと独立した期待bindingを渡す。
保存参照を先に検査し、`Pkg_Conffile_Choice.Reobserve`で全選択を現在のinode/属性/内容/退避先から
再観測する。通常Buildで原本・所有権・配置・完全tarを照合し、choiceの新しいsession参照を除く
manifest全byteと出力tarを保存物に一致させる。返却直前にも新しい選択をlive確認する。判断ADR-0107。

これは読取専用Loadとは異なり、未pinの新規観測/派生CAS objectを作ることがある。
既存のproposalを復活させたり、旧期限・保存hash・世代記録を上書きしたりはしない。
返すarchiveは一致を検証した保存物である。新規観測の期限は認可期限の更新ではない。
本番providerはroot FD、期待scope、保存選択と利用を独立して認可する必要がある。
mount/inode identityの変化、実適用後のaccepted状態、boot後の復旧は別の規則を必要とし、
現在の比較で相違を無視することはない。現状の受入は同じmount namespaceでのプロセス再起動である。

最大entry数は既存rootの524288、choiceは4096、最終tarはcallerのLimit以下かつCASの8 GiB以下。
元tarごとの既存framing上限と名前量制限、有限期限、UID0拒否を維持する。
既存の同期hash/decodeと同じく外側のプロセス資源制限も必要である。
全objectは同じStore予約で扱い、失敗時の全digest出力をzeroにする。
完了した未参照CAS objectが残り得る。生成物を返すことはpinや世代公開ではない。

このAPIは保存原本・楽観的live観測に基づく生成器であり、隠れた属性の可視性、変更者の凍結、
root/contextの真正性、署名付き同意、全managed provider、物理適用の許可を与えない。
Verifyには生存するproposalが必要で、Verify_Currentは新しい予約で全選択を再観測する。
世代保持と実root準備への接続は次節のNIAGEN06を使う。
認証済み復旧・GC・公開/bootへの接続は未完。
workerの実FS能力や全DEB効果、実ディストリビューションの認定は別の受入条件である。

## 設定済み世代 NIAGEN06

判断ADR-0108。v5の256 byte headerと元Root_Archive参照を維持し、0始まりoffset256へ
NIACRT01 digest、288へNIACRC01 digestを追加する。headerは320 byte、その後は既存の
plan/receipt各32 byteのbatchである。v6は一つの三entry batchでcatalog、tree、tree/root.tarを格納する。
NIAGEN01..05の形式・transaction導出は変更しない。設定欄を旧形式へ持ち込むことは拒否する。

保存設定の元manifest/catalog/closure、intentのroot/architecture、世代Transaction_ID、Context=Intentを
照合する。stageのroot IDは現在の設定元root IDと別である。元所有権も検証し、batchのtar digestを
設定済み出力へ一致させる。既存の世代pinで両recordを保持する。GCの型付き参照走査は別途必要である。

`Pkg_Generation_Stage`の追加generic `Observe_Configuration`は既定拒否であり、旧instantiationが
v6を暗黙に受理することはない。providerはgeneration/root/transaction/contextと保存選択、失効、phaseを
独立に認可し、設定元の借用FDと操作全体のsource排他を提供する。SDKはそのFDを閉じない。
providerの成功後も`Pkg_Generation_Configuration.Check_Current`から通常の全root照合を必ず行う。

stageのprovision/advance/inspect/prepare-root/root-preparedで照合し、Advanceの内側engineが
CASを取得する二箇所でも`Check_Inputs`を使用する。`stage:advance-inputs`での拒否はPrepare/Resumeより前に
止まる。全effectの元Authorizeも維持し、操作途中でsource排他を解放しない。
実準備は[接続手順](root-preparation.ja.md)に従う。設定適用前のsourceを使うこの経路を、
適用後のaccepted復旧に使用してはならない。公開と受理済み記録の修復は次節の別経路を使う。

## 設定済み世代の公開と受理済み記録修復

判断ADR-0109。publisherはNIAGEN06を受理し、追加generic `Observe_Configuration_Source`を
既定拒否とする。新規公開と未受理の再開では、stage検査と実公開engineのCAS予約取得後の両方で
現在sourceを全照合する。`publication:configuration`も独立認可と操作全体のsource排他を必要とする。
active transactionだけでは省略できない。保存記録の期限は新規の同意へ更新しない。

すでに要求planが実root.stateに受理されている場合だけ、別の限定型`Retained_Generation`を使う。
`stage:inspect-retained`、`stage:inspect-retained-batch`、`stage:inspected-retained`の認可と
全物理stage、pin、journal/receipt、保存閉包の照合が必要である。通常の現在証拠へ変換できない。
公開engineの予約下でtarget generation/accepted plan/catalogと完全な同一journalを再確認し、
`Commit_Pending`か`Forward_Final`の場合だけ`finish-terminal`を許可する。下位engineは全after-imageと
元health receiptを照合して記録を修復する。現在の供給trust/失効とmanaged認可も維持する。

この修復では古いsource FDを必要としない。sourceが変わっていても、新しい設定適用や公開決定を
実行するわけではない。必須record、物理tar、journalやpinが欠落した場合は状態を維持して拒否する。
`check_configured_publication.py`で実DEB、検査後source変更、accepted窓、新プロセスと欠落を検査する。
実root/boot切替や抽出後filesystemの資格確認、本番provider、mount identity移行は未完である。
