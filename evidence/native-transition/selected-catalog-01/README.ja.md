# 選択原本candidate catalogの検証

2026-09-09。基準root commit `d3e21ba`からの追加。実装境界は
[仕様](../../../native/selected-catalog.ja.md)、実行対象と結果は`report.json`。
本番catalog・依存関係成立・導入権限・実root/bootの認定ではない。

固定image `0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a`、
networkなし、通常UID1000、root拒否試験だけUID0。全実行で外側3GiB・swap0・
CPU1core・pids128制限を維持した。コマンドは`commands.json`と実行scriptに保持する。

pkgcore全source・4アプリ・22 Ada main、新313 assertionsが成功した。
元のpayload814とclaim-index449 assertionsも同じ全体実行で成功した。
26実行ファイルが独立のpath・mtime・TZでbyte一致した。516入力をcheckout・通常・
独立・sanitizedコピーへ照合し、26 ELFのPIE/nonexecstack/RELRO/BINDNOW/no-RWX-LOADを検査した。
全7repoの既存proof入力はhashとsource membershipとも不変で、重複proveはしていない。
新runtimeはSPARK対象外である。

7合成DEBを再生成して一致。4原本・3 claimの合成集合は、原本tar/CASの独立payload
検査とindex hash計算を経て、44関係項目・15 atom・全identityを独立比較した。
選択・metadata・payloadの逆順でも同一candidate hashになる。
欠落・混入・空package欠落・期待control不一致・同一identityの再梱包/別版・重複原本、
再Sealの入力変更、入力破棄、期限と非公開読取を試験した。

13元DEBと大型合成原本の154関係項目・146 atomを上流ar/codecsとPython tarfileから
独立に照合した。control archiveは圧縮byteのhash、raw controlは展開したcontrol本文のhash。
payloadも新native scanで再観測し、前回の独立tar/CAS検査に束縛された14原本集合と
fingerprintが一致することを確認した。`reference-original-index.json`は
[payload-index-01](../payload-index-01/README.ja.md)の独立検査のコピーであり、
今回の新規独立tar再検査と混同しない。原本hash一覧と大型合成入力の出自も保持する。
このnative scanは87.464秒・最大RSS36,760KiB。全OSや最大容量の認定ではない。

root拒否driverは既存1100/34/3/6、新8 assertionsが成功した。
ASan/UBSanの対象はC境界とallocator/library-call interceptionであり、Adaと上流library本体は
非計測、leak検査は無効。実行結果は`sanitized.log`と`report.json`で対象を確認する。

初期試行ではhash初期化API名を訂正し、755のテストCASが拒否された後に専用CASを700へ
設定した。readerの権限条件は変更していない。初期失敗は`attempts/`へ保持する。

選択は呼出側の主張であり、認証されたresolver結果とのguard接続は未完。
全関係・Multi-Arch・phase意味、実効owner、全効果、CAS pin閉包、世代実行・boot・
完全置換ISO・全言語翻訳も残る。大きなCAS/DEBや無制限出力はこの証跡へ複製しない。
`SHA256SUMS`は保存ファイルを対象とし、snapshot source subjectは`source-checks/report.json`にある。
