# rootアーカイブを保持する世代

NIAGEN05は、[NIAROOT1](root-archive.ja.md)を既存の世代manifestへ束縛する。
packageごとの採用claim、catalogと閉包、実tarが、世代descriptorと物理公開計画を経て
既存のManaged認可対象になる。別のinstalled DBや、root選択だけの未束縛sidecarは作らない。

## 形式と物理staging

NIAGEN04の224 byte headerに、NIAROOT1 hashの32 bytesを追加する。tagはNIAGEN05。
0起点offset224がRoot_Archive、分割recordの開始は256。既存のcatalog、closure、intent、
supply policy、stage/transaction、epoch/fenceの意味は維持する。Root_Archiveは必須で、
旧形式へ非zeroのRoot_Archiveを渡せない。旧形式のbytesとtransaction導出は変えない。
v5のbatch transactionはNIAGEN05と既存transaction ID、batch番号から導出する。

このprofileは一つのbatch、三つのentryに限定する。

| 順序 | path | 内容 |
| --- | --- | --- |
| 1 | catalog | 選択catalogの原本 |
| 2 | tree | staging directory |
| 3 | tree/root.tar | NIAROOT1から再検証した実tar |

tarを一つの通常ファイルとしてstagingするため、payload内のdevice、hardlink、全属性を
旧file-planのinode表現へ切り詰めない。格納ファイルの属性と内包されたrootの属性は別である。
これは全payloadを格納した世代成果物であり、OS rootへの展開・mount・起動ではない。

## 検査と復旧

`Pkg_Root_Archive.Verify_Target`は、明示したenclosing catalogとclosureをNIAROOT1へ照合し、
全原本と既存tarを検査して再組立て結果を比較する。欠損を再生成で隠さず、失敗出力をzeroにする。
新しいRoot_V5のCheck_Retentionは、供給policyとintentの既存検査を維持したうえで、この検査と
batchのtree/root.tar内容hashの一致を要求する。planのI/O後に期限付き原本検査を行う。

StageのProvision/Advance/Inspect/Verify_And_Hold、Publish前、StageからEngineへCAS予約を
渡した後のcomposed guard、基準世代と現在世代のnative観測に同じ保持検査が入る。
既存transaction pin → NIAGEN05 → NIAROOT1 → catalog/closure/元原本/実tarを保持する。
pinは削除しない。全履歴と全typed参照を走査する本番GCは引き続き未実装である。

新規公開の供給期限と独立policy、記録済み復旧での実root.state/WAL監査は変更しない。
公開が途中なら結果不明として扱う。保持原本が欠けた復旧を成功させない。
commit拒否後の復旧でも、現在の独立鍵/floor/ageと既存Managed guardを必要とする。

v4は既存制御状態の内部公開経路として保持する。v4をroot成果物の認定として使わない。
製品root deploymentのproviderはRoot_V5と特権展開の効果契約を必須にする必要がある。
APIがRoot_V5を読めることだけではsite認可、実effect、boot受入を満たさない。

## 変更境界の検証

元DEB三つからの組立てと実staging、pinと物理tar hash、外部catalog/closureの拒否、
rootの採用元と異なる格納内容、旧tagへの偽装、保持欠損を専用driverで検査する。
公開driverのroot-archive variantは一つの実payloadを用い、欠損拒否、commit拒否後の
結果不明、供給期限後の記録済み復旧、現在世代の保持欠損と明示復元を扱う。
独立Python読取器は実accepted stateからplan/descriptor/manifest/pinとstaged tarを辿り、
原本DEBのspanと一致することを検査する。通常CIへ同じvariantを登録する。

認可と供給observerのfixtureは人工的で、本番providerではない。特権展開、効果の実装、
起動切替・復旧、全量容量の受入、完全置換ISOは引き続き必要である。
