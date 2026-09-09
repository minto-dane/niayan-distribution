# DEBのトリガー宣言と発火先

`tools/debian_triggers.py`で原本の6種類のトリガー宣言を解析し、DEB読取器と
候補catalogへ接続した。原本のDEB・control・triggersのhashは保持する。
既存の効果契約を省略せず、未知の命令や扱えない形式は拒否する。

`state_activations`はunpackで旧版・新版の宣言を合わせ、configure、remove、purge、
deconfigure、disappearでも明示宣言から発火を計算する。トリガー処理自体と待機完了では
新しい発火を作らない。`file_activations`は変更予定の原本パスと、同じ時点で有効な
interestの成分単位のprefixを照合する。シンボリックリンクの実体をホスト上で辿らない。
スクリプトもactivate宣言も持たないパッケージによるファイル変更が、他のパッケージの
トリガーを発火する場合も扱う。

`route`はinterestとactivateの両方のawait条件を使う。片方がnoawaitなら待機しない。
自分自身のトリガーは受信できるが自分自身を待機しない。同じ受信者・名前・発火元の
発火をまとめ、後からのnoawaitが既存のawaitを消さない。
`pending`は一つの観測batchについて、受信者ごとの名前と発火元が待つ受信者をまとめる。

この処理はhandlerを実行せず、導入済みDBも書かない。呼出し側は認証済みのpackage
identityと、各段階で有効なinterest集合を渡す。既存pending/awaited状態、handler完了、
handler内の再発火、取消・再開は同じnative lifecycle/WALへ接続する必要がある。
得られた発火先だけで、全DEB効果やトランザクション完了を承認してはならない。

[遅延処理の参照状態](trigger-state.ja.md)は、この配送結果から未処理・処理中・待機を保持し、
再発火と待機解除を試験する。handlerを起動する稼働実装ではない。

## 現在の入力範囲

宣言は1 MiB・4,096行まで。ファイル変更batchは65,536パス、合計16 MiB、深さ64まで。
受信登録は4,096パッケージ・合計65,536宣言、配送は262,144組まで。
相反する重複宣言、非正規パス、空白を含むファイルトリガー、扱えない明示名は拒否する。
これらはNiaの現在の採用範囲で、あらゆるDEBを受理できるという主張ではない。
全rootを一つの無制限配列へ入れず、後続のnative状態機械へ有界batchで接続する。

基準は[Debian 13のトリガー宣言](https://manpages.debian.org/trixie/dpkg-dev/deb-triggers.5.en.html)と、
上流[トリガー仕様](https://sources.debian.org/src/dpkg/1.17.25/doc/triggers.txt/)の
ファイル名の字面による照合規則。古い仕様の参照を現行全体の受入に読み替えない。

試験は9通りのawait組合せ、6つの発火境界、自己発火、成分prefix、同一batchの集約、
原本DEBから候補catalogへの接続、不正入力を検査する。旧ISOから保持した1,186個の
triggersもhashを確認して解析する。これらのhandlerを実行した結果ではない。
