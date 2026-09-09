# 原本payload保持の検証

[report.json](report.json)が対象sourceと検証範囲を記録する。
固定Debian 13環境でpkgcoreの全ソース・4アプリ・20 Ada mainを検査した。
新payload試験814 assertionsがC.UTF-8とCの両caller localeで成功し、locale復元も確認した。
40合成DEBの再生成byte列・manifestが一致した。
通常・空ファイル、directory、前方hardlink chain、symlink、device/FIFOの観測、
permission/UID/GID、時刻、xattr/ACL/flag、Unicodeと非表示文字を含む名前を検査した。
重複・祖先競合・危険path/link・欠落/循環・不正ACL・未知属性・量的上限・破損と期限を拒否した。

最終バイナリによる[11合成入力・28 entry](retained-fixtures-oracle.json)と、
[13元DEB＋大型合成DEB・2,904 entry](retained-originals-oracle.json)を独立oracleへ照合した。
Debianの読取工具でtarを得て、Python tarfileによる内容・属性・リンク・正確なPAX時刻と比較し、
個別content・属性blob・原本・tarのCAS全hashを検査した。ファイルシステムへの展開や実行は行わない。
元DEBの対応filenameとhashは[入力](original-media-inputs.json)、大型入力は[生成記録](large-input.json)。
供給認証や、全Debian packageを検証したことを意味しない。

14入力の展開量は計166,123,520 byte。大型tarは100,669,440 byteで、
[各native子processの計測](retained-originals/resources.json)の最大RSSは16,640 KiBだった。
各probeは別の計測processから起動した。当該入力の測定で、全形式のメモリ証明ではない。
名前・entry数・extension・属性blobの上限と外側resource scopeを維持する。

[二ビルド](reproducibility.json)の24実行ファイルは別パス・入力mtime・TZで全byte列が一致した。
[494入力](build-inputs.json)をcheckout・通常・独立・sanitizer用コピーへ照合した。
[24 ELF](elf.json)のPIE・非実行stack・RELRO・即時binding・非RWX LOAD、
[root拒否](root-probe.log)3 assertionsも成功した。
ASan/UBSanをリンクした試験でも814 assertionsが成功した。
C境界とallocator/library-callの検査であり、Adaと上流libraryのコードは非計測、leak検査は無効。
[実行条件](commands.json)に区別する。

[初期試行](attempts/)も保持する。コンパイル時の型可視性、ASCII専用出力型、
C localeでの変換失敗、負の小数時刻、ACL qualifierの符号変換、不正ACLの黙認、
Unicode正規化による名前の変更を検出して修正した。
途中の候補ビルド・独立oracleの不一致は最終成功へ混ぜない。
上流ソースを変更せず、原本の名前・時刻をnative側に保持する。

ソース24工程は[最初](source-checks-first/report.json)と[最後](source-checks-final/report.json)で成功し、
前後subjectは`32956b52274683d893c1d0c5824d22e45b4ea8f25daa1af78370666a37fa90bc`で一致した。
全7repoの[proof入力](proof-input-comparison.json)は不変で、新runtimeはSPARK対象外である。
重い検証は一つずつ、3 GiB・swapなし・CPU 1コア分・128プロセスに制限した。

この結果は[採用profileの観測SDK](../../../native/deb-payload.ja.md)の検証である。
global PAX・sparse・残るACL方言、世代形式と実行器・全所有権・全DEB効果、
稼働catalog/認可・実root/boot・完全置換ISO・全言語翻訳は引き続き未完。
