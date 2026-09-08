# ISO 09/10の再構築比較 — 一致

2026-09-08。同じ入力から、新しいbootstrap環境とインストーラー取得をそれぞれ行った2回のビルドが完了し、ISO全体が一致した。認証済みDEBキャッシュと、別の独立再ビルドで検証した独自DEBは再利用した。bootstrap stageとインストーラーkernel/initrdのキャッシュは再利用していない。

- ISO: `niaos-0.1.0-amd64.hybrid.iso`
- サイズ: 3,637,100,544 bytes
- SHA-256: `d4c18dc0e2be653bf11a04db40db95ca0353322010133e068dda274bd4aa314b`
- 入力manifestのSHA-256: `a6c4f7b9be5c579a9f0952df15276881cb48284f36bb13bdc793ad4ef180cf3b`
- 実バイト列の`cmp`終了値: 0

[比較結果](iso-comparison.json)の`first`は10、`second`は09。実行した`record-build.py`も保存した。比較工具は入力manifest・ISO集合・サイズ・SHA-256と実際の`cmp`を検査し、不一致なら非0で終了する。09のISOはホストへのコピー後にも同じSHA-256を確認した。

05/06と07/08の不一致から、APTとAppStreamの再生成可能なキャッシュをlive-build標準のrootfs除外設定に追加した。上流ソース、AppStream実行ファイル、live-buildスクリプトは変更していない。2,239件のLive package一覧も以前の候補と一致した。

ビルダーは固定したDebian cloud imageと署名付きAPT snapshot、1 vCPU・2 GiBのVMを使用した。VM全体をメモリ3 GiB・swapなし・CPU 1コア分・128プロセスの外側kernel制限内で動かし、ビルドは順番に実行した。追加のソース収集工具を導入する前に、ビルダーのパッケージ版と比較結果を記録した。

これは記録した2回のビルドについての結果であり、異なるマシン・入力・将来版へ一般化しない。起動・導入の受入、対応ソースの収集、実機や本番の認定は別の記録で確認する。`build-record-10/`はペイロードを除いた設定・版・hashの抜粋で、ISO・DEB・udeb自体はGit外に保管する。
