# 選択原本に束縛したcandidate catalog

`pkgcore/runtime/pkg_selected_catalog`は選択候補のmetadataと全payload主張を結び付ける
private native SDKである。稼働catalogの第二の権威や導入済みDBを作らない。

## 入力と失敗

`Add`はCAS中の元DEB digestを受け、envelope/control/field/identity/関係構文を既存native
readerで再検査する。公開のObservationや書き換え可能なMetadata recordを信用しない。
原本・圧縮control archive・raw controlのhash、name/version/architecture/source identity、
Multi-Arch、Essential/Protected、Installed-Sizeの有無と値をcompactに保持する。
DependsからStatic-Built-Usingまで全11項目のatomと代替groupを順序通り保持する。

`Seal`へ選択した各原本と期待するraw control hash、およびsealed payload索引を渡す。
選択・metadata・payloadの原本集合は重複なく完全一致しなければならない。空payloadの
packageも集合の一員であり、個数だけの比較やcontrolが同じ別原本への置換では通らない。
同じname/architectureの二版・再梱包は拒否する。同名の別architectureを保持することは
共存可能との認定ではない。name/versionの表示やlocaleを照合キーにしない。

未Sealの候補から原本・関係・hashを読めない。Add/Sealの失敗は候補全体をClearする。
繰返しSealでも全入力を再照合する。追加・選択・payloadの順序は結果を変えない。
入力payloadをClearしても候補のmetadataとhashは変わらないが、そのpayloadは
`Matches_Payload`を満たさなくなる。候補は元のfingerprintを保持する。

最大4096原本・262144 atom・文字列合計64MiB。各原本に1MiBのDocumentや
各fieldに固定長Expressionを保持せず、検査時だけ一時領域を使う。上限までの実負荷受入と
有限入力の計測を区別する。UID0を拒否し、期限と外側3GiB/CPU1core/swap0/pids128制限を使う。
同期I/O中の即時キャンセルは外側の実行期限も必要とする。

## Fingerprint v1

SHA-256へ順に、8byte big-endian長とASCII `NIACSEL1`、32byte payload索引hash、
8byte big-endian原本数を渡す。原本digestのbyte順で、各原本の32byte original、
32byte compressed control archive、32byte raw controlを連結する。
metadata/atomは束縛したraw controlとversionを持つparserから導出する。
これは永続catalog schemaでも、source authenticityの証明でもない。

## 接続条件

選択リストは呼出側の主張であり、認可されたresolver集合との接続は未完である。
最終集合のDepends/Pre-Depends/Conflicts/Breaks成立、Multi-Arch共存、Replacesによる
実効所有権、unpack/configure順序・既存状態、全効果、CAS pin閉包、catalog/guard・実root/bootは
別の必要条件として残る。関係の保持を関係成立へ、Sealを実行許可へ読み替えない。

意味実装は[Debian Policyの関係仕様](https://www.debian.org/doc/debian-policy/ch-relationships.html)と
[control仕様](https://www.debian.org/doc/debian-policy/ch-controlfields.html)に照合する。
現行Web文書と固定Trixie実装の差は別に確認する。`:any`、Architecture:all、versioned Provides、
Pre-Dependsの既構成版などを単純な名前集合へ平坦化しない。

## 検証記録

固定環境の全source・4アプリ・22 Ada mainと新313 assertionsが成功。
26実行ファイルは場所・時刻・TZの異なる二ビルドで一致し、516入力を照合した。
4合成原本の44関係項目・15 atomと逆順hash、13元DEBと大型合成原本の154項目・146 atomを
独立に比較した。後者のnative processは87.464秒、最大RSS 36,760KiBだった。
最大容量や全OSの実負荷受入ではない。詳細と追加の境界検査は
[検証記録](../evidence/native-transition/selected-catalog-01/README.ja.md)を参照。
