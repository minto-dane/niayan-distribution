# Nia管理コマンドの実装状況

製品判断は[0003](../docs/decisions/0003-management-interface.ja.md)。
追加の対象と採用境界は[調査記録](command-review.ja.md)とコマンド台帳を参照。
`package_cli.py`は12コマンドの引数を、未認証の構造化された操作要求へ変換する。
`epkg -e`のローカル作成と`emgr -d`の表示は[成果物工具](interim-package.ja.md)へ接続した。
`emgr_download_ifix -L URL [-P DIRECTORY]`は[共通の供給認証](repository.ja.md)を使い、
あらかじめ配備されたroot所有policyと信頼cacheに従って成果物を取得する。
稼働実行器やcatalogには接続していない。`bin/`は開発用の入口であり、
パッケージやISOには組み込んでいない。稼働状態の変更・照会・事前検査は終了値1で未接続を返す。
ローカル成果物操作の成功とヘルプは終了値0、構文エラーは2となる。

```sh
native/bin/installp --help
native/bin/lslpp --help
make native-check
```

公開コマンドの代替として、Python工具名を製品の操作手順へ載せない。
開発用入力検査器と実行器の内部プロトコルは、利用者向けコマンドとは分ける。

現在解析する構文は各`--help`が正本。結合短縮オプションと値の直結を扱う。
`geninstall -I`は文字列をshell実行せず、対応する`installp`の要求へ変換する。
パッケージ名と版はDebian原本を維持する。パターン、リストファイルは解析器では
展開・読取せず、catalogに接続した後の意味検査が担当する。

`installp -p`は事前検査、`instfix -p`は修正に必要なパッケージの表示、
`lppmgr -p`は移動・削除時の確認として区別する。`lslpp -h`は履歴である。
`suma`の`Action=Preview`を保存・予約しても、タスク保存自体が読取操作になるわけではない。
`inutoc`の既定対象は`/usr/sys/inst.images`である。

未対応オプションは無視せず拒否する。現在は適用時の`-d`を必須とし、
`installp -C`の不要な引数、`-u all`、曖昧な重複指定も拒否する。
容量自動拡張、別root、復旧保存の省略、検査結果で正本を上書きする操作は未接続である。
これらの制限が残るため、参照した操作体系との完全な構文・動作互換性は未達。

応答も適合対象であり、表示列・状態名・結果要約・プロンプト・終了コード・
stdout/stderr・機械処理形式・対話画面を固定fixtureで照合する。
現在の未接続エラーとヘルプは開発用で、最終応答の適合試験には数えない。

`emgr`・`epkg`の稼働操作は単一catalogへの接続が未完。
`smit`・`smitty`の画面は未実装。systemd等の外部管理工具を包むコマンドは作らない。
現在のコマンド台帳は全管理コマンドの完全な一覧でも、実行許可の台帳でもない。
