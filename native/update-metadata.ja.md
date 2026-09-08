# 更新緊急度と修正告知の識別

通常DEBの特別な緊急修正形式は定義しない。Debianの`Urgency`には
`low`、`medium`、`high`、`critical`、`emergency`があり、`.changes`やchangelogで扱う。
`DEBIAN/control`の`Priority`は導入上の重要度であり、更新緊急度ではない。
[Debian Policy](https://www.debian.org/doc/debian-policy/ch-controlfields.html#urgency)。
アップロード緊急度はtestingへの移行速度にも使われ、脆弱性の深刻度とは分ける。
[開発者向け指針](https://www.debian.org/doc/manuals/developers-reference/best-pkging-practices.en.html#selecting-the-upload-urgency)。

`update_metadata.py`は元DEBを既存のreaderで検査し、指定された平文`.changes`について
ソース名・ソース版・バイナリ版・architectureと実DEBのSHA-256/サイズを照合する。
緊急度は大文字小文字を正規化し、コメント付き原文と欠落状態も保持する。
未知の緊急度を通常更新へ変換しない。

DSA-listの対象release/ソース行から、修正ID、告知に記載されたCVE、修正ソース版を
識別する。比較はDebian版順序を使い、binNMUのバイナリ版とソース版を混同しない。
修正告知のJSON一覧にはDSA番号が含まれないため、DSA-listは別入力である。
[公式セキュリティ情報](https://www.debian.org/security/index.html)。

```sh
python3 native/update_metadata.py --deb /input/package.deb \
  --changes /input/upload.changes --advisories /input/DSA-list \
  --output /new-output/update.json
```

これは開発用の読取工具であり、発行者・署名・時刻・失効を認証しない。
出力には入力digestと認証未実施を明記し、実行許可は常にfalse。
版が告知された修正版以上でも、全脆弱性が解消されたとは判定しない。
一致なし、告知未提供、緊急度なしは安全・通常・低緊急度の証拠にしない。
全tracker JSON、DLA、変更履歴の自由文解析、DSAの全歴史形式、稼働catalogへの接続は未完。

製品接続では、署名済み配布索引→原本DEBと、出典・取得時刻・失効・完全性を
確認した告知を同じ対象へ結び付ける。`instfix`と更新画面がその結果を共有する。
`Pkg_Advisory`の深刻度・適用条件・失効世代を`Urgency`から推測して埋めない。
独立した暫定修正成果物の`epkg`/`emgr`経路は[製品判断](../docs/decisions/0003-management-interface.ja.md)に従う。
