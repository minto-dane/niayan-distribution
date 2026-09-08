# 配布物のソース補完

このディレクトリは完成した配布物の記録・ソース保管の工具を置く。ISOへ組み込む入力ではない。

`image/collect-sources.py --include-installer`の完了後、専用ビルダーVMで次を実行する。

```sh
sudo python3 release/complete-sources.py --sources /build/corresponding-sources
```

収集時の工具を別の場所へ固定した場合は、`--collector /固定した場所/collect-sources.py`を指定する。base reportに記録された工具のSHA-256と一致しなければ停止する。base reportと取得済みソースは変更せず、`signed-kernel-sources/`へ補完記録と不足アーカイブを保存する。`--resume`は同じbase report・工具だけを受け付け、保存済みファイルも再照合する。

Debianの署名用Linux source packageにはLinux本体が含まれず、生成された`source-template/debian/control`が本体の正確な`Built-Using`を記録する。一方、インストーラーのkernel/module udebはこのフィールドを持たない場合がある。ISO 09ではLiveのLinux 6.12.107-1に加え、内蔵インストーラーのLinux 6.12.94-1も必要だった。

工具は元の記録で署名用source archiveのハッシュを確認し、archive内の通常ファイル1件だけを読む。版番号の接尾辞から推測したり、上流のソースや制御ファイルを書き換えたりしない。不足する本体は同じ署名付きAPT snapshotから取得する。APTに正確な版がない場合のみ、元の収集工具のdebsnap HTTPS取得とDSC照合を使い、その経路を別のprovenanceとして記録する。

対象は現在のamd64 Debian 13プロファイルの署名済みLinux。未知の形式・不明な参照を無視して成功にしない。配布時はbase collectionとこの補完の両方を含め、コピー後に全アーカイブを照合する。
