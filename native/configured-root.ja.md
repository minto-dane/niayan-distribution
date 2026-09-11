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
先に保持recordのheader/順序/全member/hashを検査し、再構築結果のmanifestと保持digestを比較する。
正しい保存閉包が指す欠損を、検証中に原本から再生成して成功扱いしない。
再構築が必要ならcallerが別のBuildを明示的に行う。旧記録を書き換える復旧APIではない。

## 実行境界

最大entry数は既存rootの524288、choiceは4096、最終tarはcallerのLimit以下かつCASの8 GiB以下。
元tarごとの既存framing上限と名前量制限、有限期限、UID0拒否を維持する。
既存の同期hash/decodeと同じく外側のプロセス資源制限も必要である。
全objectは同じStore予約で扱い、失敗時の全digest出力をzeroにする。
完了した未参照CAS objectが残り得る。生成物を返すことはpinや世代公開ではない。

このAPIは保存原本・楽観的live観測に基づく生成器であり、隠れた属性の可視性、変更者の凍結、
root/contextの真正性、署名付き同意、全managed provider、物理適用の許可を与えない。
Verifyには生存するproposalが必要で、再起動後のdurable loader/復旧、世代保持・GCへの接続は未完。
後段の生成形式・実root準備・公開/bootにも新形式を明示的に接続する必要がある。
workerの実FS能力や全DEB効果、実ディストリビューションの認定は別の受入条件である。
