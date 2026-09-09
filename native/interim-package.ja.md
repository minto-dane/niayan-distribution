# Native緊急修正成果物

`interim_package.py`は、元のDEBを変更しない決定的な作成器・読取器である。
`epkg`のテンプレート作成と`emgr -d`の内容表示へ接続した。
`emgr_download_ifix`の[共通供給認証](repository.ja.md)では、外側のTUF署名と
契約・対応ソース参照の原本バイト列を検証する。稼働中の対象版照合、保留、適用・削除は未接続である。
この成果物を構文検査できたことは、信頼や実行許可を意味しない。

## 開発用入口

```sh
native/bin/epkg -e /build/fix/control.json -w /build/output fix001
native/bin/emgr -d -e /build/output/fix001/fix001.HASH.epkg
native/bin/emgr -dv3 /build/output/fix001/fix001.HASH.epkg
```

`HASH`は成果物全体のSHA-256で、作成時に実パスを表示する。
`-w`の既定は`$HOME/epkgwork`。その下のlabelディレクトリに新規出力する。
同名ファイルを上書きしない。元DEBはcontrolと同じディレクトリに
`<artifact_sha256>.deb`として配置する。labelはcontrolとコマンド引数の完全一致を要求する。
出力を作る前にcontrolを一度読み、全DEBとそのidentityを検査する。
入力・出力の親を含むsymlinkをたどらず、出力は一時ファイルから排他的に公開する。
I/O障害は失敗として返す。公開後の同期に失敗した場合には出力が存在し得るため、
非ゼロ終了を「成果物が存在しない」と解釈しない。

現行controlは以下のnative JSON形式である。外部形式のcontrol、BFF、圧縮tarを
同じ形式として読み込まない。拡張子も圧縮を意味する`.Z`を付けず`.epkg`とする。
対話作成、追加オプション、外部環境との出力一致は未受入である。
`emgr`のインストール・一覧・検査・削除・lock照会は、接続完了まで終了値1となる。

## v1形式

| 要素 | 表現 |
| --- | --- |
| 識別子 | ASCII `NIA-INTERIM`、バイト`00 01` |
| manifest長 | big-endian unsigned 32 bit |
| manifest | canonical JSON。キーをsort、ASCII escape、空白なし、浮動小数点なし |
| 各DEB | SHA-256の32バイト、big-endian unsigned 64 bitの長さ、DEB原本 |

DEBはdigestの昇順に配置し、manifestが指すbase・targetの集合と完全一致させる。
末尾の追加データ、欠落、重複、非canonical JSON、identity・ハッシュ不一致を拒否する。
manifest 256 KiB、各DEB 128 MiB、DEB合計256 MiB、置換64組が上限である。
展開後にも既存DEB読取器の容量・パス・member検査が適用される。
対象はTrixie/amd64、元DEBのarchitectureはamd64又はallに限る。

manifestの必須キーは次のとおり。追加キーは拒否する。

| キー | 内容 |
| --- | --- |
| `schema` | `org.niaos.interim-package/v1` |
| `label` | 1〜100 ASCII文字。先頭英数字、残り英数字・`_.+-` |
| `description` | 1〜1024文字の説明 |
| `release`, `architecture` | `trixie`, `amd64` |
| `created_at`, `expires_at` | 正の整数秒。expiryはcreationより後 |
| `security_epoch` | 正の整数 |
| `advisories` | CVE・DSA・Nia修正IDの非空集合。昇順・重複なし |
| `requires`, `conflicts`, `supersedes` | 関連する成果物SHA-256の集合。各64件以下 |
| `rollback_contract_sha256` | 復旧契約の参照 |
| `replacements` | 同じpackage/architectureに属するbase・targetの対。名前順・重複なし |

各置換には`base`、`target`、`effect_contract_sha256`、`activation`が必要。
base/targetは`package`、`version`、`architecture`、`artifact_sha256`、
`source_manifest_sha256`を持つ。版はepochを含むDebian原本の文字列を維持する。
同一artifactへの置換、異なるpackage/architectureへの置換は拒否する。
`requires`と`conflicts`又は`supersedes`の重複も拒否する。

activationは`new-process`、`service-restart`、`relogin`、`node-reboot`、
`offline-migration`のいずれか。これは作成者の宣言であり、活性化完了の観測ではない。
未受入のカーネル同時更新を表すモードは設けていない。

## 信頼・応答・受入

ローカル作成・表示自体は署名検証を行わない。供給時にはTUFの署名対象として公開する。
共通intakeは署名・委譲・metadata版・期限・security epochと参照バイト列を検査する。
契約の意味、Debian archiveの信頼chain、稼働baseとの一致、実効果の閉包は、
通常パッケージと同じcatalog・managed engineへ接続して検査する必要がある。
別の修正DBや特権Python writerは作らない。

表示は元DEBのファイル一覧とサイズ・digest、宣言された対象版・activationを使う。
制御・Unicode format文字は表示時だけescapeし、原本のハッシュを変えない。
レベル1〜3の項目は開発用に試験しているが、参照環境との列幅・全文・locale・
プロンプトの適合fixtureは未取得。完全な応答互換性を宣言しない。

`test_interim_package.py`と`test_interim_commands.py`で、原本保持、決定性、
破損・曖昧入力の拒否、実コマンドの作成と表示、出力上書き拒否を検査する。
空のPATHでも実行し、別の管理器に依存していないことを確認する。
これらは稼働更新、電源断復旧、署名失効やTUIの受入を代替しない。
