# Native最終集合の必須関係検査

2026-09-09。基準root commit `ef2ca13`からの追加。
[仕様](../../../native/final-set.ja.md)と`report.json`に範囲を定める。
候補の関係検査であり、実行順序・認可・全効果・実root/bootの受入ではない。

固定image `0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a`、
networkなし、UID1000（root拒否試験のみUID0）。外側3GiB・swap0・CPU1core・pids128を維持した。
全source・4アプリ・23 Ada mainが成功し、新規23038 assertionsを含む。
898ケースの期待値・raw original/control・空payload source index・catalog・architecture policy・
receipt hashを独立計算で比較した。失敗ではreceipt hashがすべてゼロであることも確認する。

153個の小さな合成DEBはpayloadが空で、maintainer scriptを持たない。
再生成検査、native matrix、独立hash計算、固定上流simulationは生成された通常CI runnerにも
組み込んだ。テスト対象外の全DEBや最大capacityまで認定したと解釈しない。

上流dpkg 1.22.22をprivateな模擬statusと別rootへ向け、各targetのconfigureとunpackを
`--simulate`で検査した。statusが変更されなかったことを毎回照合した。
Niaのbackendや第二の導入済みDBには使っていない。これらは候補の全packageが存在する
模擬状態からの個別照合であり、実transactionの順序やPre-Depends cycleの導入可能性は証明しない。
初期610ケースでは、同名で別architectureの自己Breaksだけが異なった。その結果と詳細を
`attempts/`へ保持し、instance単位のBreaks例外へ修正した。
negative virtualのarchitecture指定も加えた898ケースでは全件一致した。

上流各ケースの記録は`upstream-cases.jsonl`へまとめた。各行のrecordをPython標準jsonの
indent=2と終端改行で復元するとsha256欄の元result.jsonになることを検証している。
privateな模擬root・statusは複製しない。全引数・手順は保持したscriptとcase fixtureにある。
上流出力の成功を任意のscript実行・全runtime効果の受入へ読み替えない。

27実行ファイルが異なるpath・mtime・timezoneのビルドでbyte一致し、677入力をcheckout・
通常・独立・sanitizedコピーへ照合した。27 ELFのPIE/nonexecstack/RELRO/BINDNOW/no-RWX-LOADも成功。
root拒否driverは既存1100/34/3/6/8と新5 assertionsが成功した。
ASan/UBSanリンク下でも23038 assertionsが成功した。ただしC境界とallocator/library-call
interceptionの検査であり、Adaと上流library本体は非計測、leak検査は無効。
全7repoの既存SPARK入力はhash/membershipとも不変。新runtimeはSPARK対象外である。

初期コンパイルではテスト用匿名aggregateのループとrecord aggregateを修正した。
その試行ログも保持する。ソース整合性の対象hashと結果は`source-checks/report.json`、
保存ファイルの完全性は`SHA256SUMS`。最大原本/atom容量・全OSの負荷受入は未実施。

認証済みresolver/policyと同意への接続、実際のphaseと既構成版、Essential/Protected削除、
source保持・weak依存policy、実効所有権・全効果・CAS pin閉包、稼働catalog/guard・
世代実行・boot・完全置換ISO・全言語翻訳は残っている。
