# 選択候補のnative関係検査

`pkgcore/runtime/pkg_deb_final_set`はsealedな`Pkg_Selected_Catalog`を受け、候補集合の
必須関係と共存条件を検査する。成功は実行認可ではなく、検査範囲をversionで定めた
private receiptである。control・payloadや第二の導入済み状態を書き換えない。

## 関係とarchitecture

DependsとPre-Dependsは、すべてのcomma groupについて少なくとも一つの代替候補が
実名またはProvidesによって充足される必要がある。提供元のpackage版と仮想packageの
提供版を混同しない。版のないProvidesは版付き依存を充足しない。複数の提供版も保持する。
比較には既存nativeのDEB version orderを使う。

binary依存の無指定architectureは依存元のarchitectureであり、Architecture:allはnativeに
対応する。Multi-Arch:foreignの提供元は無指定依存を別architectureからも充足できる。
`:any`はMulti-Arch:allowedの条件を持ち、任意のexplicit architectureとは区別する。
Provides自身のarchitectureも保持し、その`any`ラベル同士の一致も固定実装に照合する。
source template用の`:native`をbinary関係の別名へ変換しない。

enabled policyにないpackage architectureは拒否する。allは独立packageのラベルであり、
nativeやenabledの具体的ラベルには指定できない。nativeはenabledへ明示的に含める。
これらは呼出側のpolicy入力で、実hardware・foreign executableの実行能力の認定ではない。

同名で異architectureのpackageはすべてMulti-Arch:sameで、DEB比較で同じ版である必要がある。
これだけで共有ファイルの内容・属性や実効所有権まで認めるものではない。

Conflicts/Breaksは対応する他のcapabilityが存在すると拒否する。固定上流unpackの
negative virtual関係は名前と提供版で判定され、architecture指定で対象を限定しない。
実名のnegative関係はarchitectureを照合する。Conflictsの自己名例外は同名instance集合に
及ぶ一方、Breaksのconfigure検査は宣言元自身だけを除き、同名の別architectureも検査する。
この違いは610ケースの初期比較で実測し、898ケースへ拡張して照合した。

参照は固定[deb-control(5)](https://raw.githubusercontent.com/guillemj/dpkg/1.22.22/man/deb-control.pod)、
[architecture/version matcher](https://raw.githubusercontent.com/guillemj/dpkg/1.22.22/lib/dpkg/depcon.c)、
[configure関係検査](https://raw.githubusercontent.com/guillemj/dpkg/1.22.22/src/main/packages.c)、
[unpack関係検査](https://raw.githubusercontent.com/guillemj/dpkg/1.22.22/src/main/depcon.c)、
[共存版検査](https://raw.githubusercontent.com/guillemj/dpkg/1.22.22/src/main/configure.c)。
文書だけからphase間の挙動差を消さず、上流原本を改変しない。

## 結果と制限

名前からproviderを引くcompactな索引を使う。原本のcanonical順・field順・atom順で
検査し、同じ入力では同じ最初の原因と原本IDになる。エラー表示文は持たず、UIで翻訳できる
Finding_Kind、field、group、atom位置と原本digestを返す。

失敗時は成功receiptの全hashをゼロへ戻す。成功時のarchitecture hashは8byte big-endian長と
ASCII `NIADARCH1`、同形式のnativeラベル、8byteラベル数、昇順に各長付きラベルを
SHA-256へ渡す。結果hashは長付き`NIADFINAL1`と32byte candidate hash、32byte
architecture hashをSHA-256へ渡す。順序の変更はhashを変えず、policyの集合変更は変える。

最大256 architecture、既存candidateの4096原本・262144 atom上限と外側3GiB/CPU1core/
swap0/pids128制限を維持する。UID0を拒否し、全体成功までreceiptを公開しない。
最大容量の実負荷と有限fixtureの検査は区別する。

## 残る接続

これは候補集合の検査であり、unpack/configureの順序、過去の構成版・削除状態、
Pre-Depends cycleの導入可能性を証明しない。weak依存はplanner policy、Built-Using等は
source保持、Replacesは所有権の条件として別途扱う。Essential/Protected削除や
必須base systemの完全性には既存世代と製品policyの検査が必要である。

認証されたresolver集合・policy・同意、稼働catalog/guard、実効owner、全script/trigger等の
効果、CAS pin閉包、世代実行とbootへの接続は引き続き必要。
上流シミュレーションのprivate statusは試験専用であり、Niaの製品backendではない。

## 検証記録

固定環境の全source・4アプリ・23 Ada main、新23038 assertionsが成功した。
153原本の898ケースについて独立hash計算と固定上流simulationが一致した。
27実行ファイルが独立二ビルドで一致し、677入力を4コピーへ照合した。
root拒否5 assertionsとASan/UBSanリンク下23038 assertionsも成功した。
Adaと上流library本体は非計測、leak検査は無効。全7repoのproof入力は不変。
[証跡](../evidence/native-transition/final-set-01/README.ja.md)に対象と未認定範囲を記録する。
