# 既存世代からのnative変更集合

`Pkg_Deb_Transition`は二つのsealed候補を照合し、通常更新の変更集合を返す。
前後の原本・control・payloadは既存catalogの完全照合に従う。
稼働世代の認証や書込権限は、この読取SDKの出力だけでは成立しない。

## 検査

正確なpackage nameとarchitectureで照合し、原本が同じなら変更なしとする。
新規追加、削除、Debian版比較による更新/降格、同等版の別原本への再梱包を区別する。
`2`と`2-0`は同等版だが、原本が違う場合は変更として残る。
architecture変更は削除と追加になる。結果はname、次にarchitectureのbyte順に並ぶ。

targetの全必須関係・共存条件を`Pkg_Deb_Final_Set.Check`で検査する。
前世代はsealedでなければならないが、壊れた依存集合からの修復を認める。
既存catalogは非空世代を表すため、空世代からのbootstrapは本APIの対象外である。

前世代にEssential又はProtectedの指定があれば、同じidentityと各flagの維持を要求する。
削除、architecture変更、flagの消失は`Protection_Migration_Required`/`Denied`で拒否する。
異名packageのProvides/Replacesはidentity保持の代わりにならない。
削除の保護は[固定dpkgのcontrol仕様](https://raw.githubusercontent.com/guillemj/dpkg/1.22.22/man/deb-control.pod)を参照した。
flag消失も拒否する点はNiaの通常更新policyであり、上流の更新動作との同一性ではない。
APT/dpkgからの移行等には、必要な機能の代替と起動・復旧を検証する別の移行契約が必要である。
単純なforce又はcallerの承認booleanは用意しない。

## 結果と束縛

全体成功時だけsealed planを返し、変更ごとにname/architecture、前後version、前後原本を保持する。
失敗時は旧成功計画も部分計画も消し、言語に依存しないfindingを返す。
入力順や入力catalogの寿命に依存しない。UID0でのBuildは拒否する。

fingerprintはSHA-256で、次の順のbyte列を対象とする。数値はu64 big-endian、
Textはbyte長のu64とUTF-8 byte列、Digestは32 byteである。

1. Text `NIADTRANS1`、前catalog Digest、後catalog Digest、target final-set receipt Digest。
2. 変更数、順序付けた全変更。
3. 各変更はkind数値（Added=0、Removed=1、Upgraded=2、Downgraded=3、Repacked=4）、
   name、architecture、前version、後versionのText、前後原本Digest。

不存在側のversionは空文字列、原本はzero digest。変更なしの計画も完全な束縛を持つ。
各catalog最大4096packageに対し変更は最大8192件。外側の3GiB/CPU1core制限も維持する。

## 検証範囲と接続条件

36合成原本・44ケースを通常CIで実行し、別のPython読取器が元ar/controlから
前後source index、catalog、target receiptと全deltaのhashを計算する。
試験世代には共通の変更されない通常packageを含め、非空catalog契約を保つ。
試験原本は空payload・scriptなし。製品の導入済みDBやwriterは作らない。

本番admissionではguard下でBefore_Hashと実際のaccepted generationを一致させる必要がある。
降格の分類はrollback floorの許可ではない。実行phase、過去の構成版、保護移行、
所有権・全効果・CAS pin閉包・実root/bootへの接続は未完である。
