# Nia取り込みプロトコル v1

> 保存した独自カタログ研究モデルの文書です。Debian 13の実配布方針は[現在の設計判断](decisions/0001-debian13.ja.md)を参照してください。この文書の機能が実イメージへ接続済みであるとは扱いません。

規範は各`tools/*.py`のstrict field setと本仕様。入力はネットワークから切り離した非特権build-roomで扱う。受信したJSONの`true`が権限証明になることはない。全出力の`execution_permit=false`を保つ。

## Input tree
`SNAPSHOT/dists/forky/InRelease`、署名本文が列挙する`main/binary-amd64/Packages.xz`等、`main/source/Sources.xz`等、対応する`pool/...`を用意する。全pathは相対、リンク/特殊ファイル/traversalを拒否する。秘密鍵、実ノードの資格情報、APT/dpkgの作業DBは不要。

`verify-deb`のINDEXは`dists/forky`からの相対パス、DEBはsnapshot rootからの相対パス。`.deb`自身の内部metadataもPackagesと一致しなければならない。profileはamd64/allのみ。`verify-source`は同じ署名ReleaseのSourcesからsource名・版・Binary対応と全source fileを検査する。`.dsc`のuploader署名は別の保証であり、本実装のarchive chainとは区別する。

## Trust object
```json
{
  "schema": "org.niaos.debian-trust/v1",
  "keyring_sha256": "<exact-keyring-sha256>",
  "primary_fingerprints": ["<independently-provisioned-primary-fingerprint>"],
  "minimum_signatures": 1,
  "now": 0,
  "max_age_seconds": 86400,
  "future_skew_seconds": 60
}
```
この記述のplaceholderとnow=0は無効であり、実運用設定ではない。信頼するkeyring/digest/clockは受信snapshotの自己申告から生成しない。現在の鍵失効・trusted time・monotonic floorは別の管理器の責任。Release期限切れを自動で許すarchive modeはない。gpgvの成功コードだけでなくVALIDSIGのprimary、hash algorithm、期限、必要な署名数を検査する。gpgv/libzstdは未検証TCB。

## Compose request
必須fieldは`profile_sha256`, `inrelease_sha256`, `required_packages`, `inputs`。inputsの各項目は`index`と`deb`だけ。profileは現行`nia-os.json`の正確なfile bytesのSHA256と照合し、Releaseの期待値を外部の現行Nia policyから取得する。最大4096 DEBを再読取り・再認証しmainだけを受け入れる。候補catalogはno scripts/no filesystem writesで生成する。indexに存在する全パッケージを使うものではない。

候補にはfile ownership, conffile intent, exact control members, effects, unknown metadataを保持する。ファイル衝突の無条件Replaces解消は行わない。同じdirectoryだけ属性一致時に共同所有候補とする。現在は最終集合checkのみで、unpack/configure/trigger orderやinitramfs生成の証明ではない。

## Reproduction subject
`deb_sha256`, `source_manifest_sha256`, `buildinfo_sha256`, `package`, `version`, `architecture`をexactに固定する。buildinfo Versionはsource versionなのでbinNMU版を勝手にtrimしない。正確なDEBのSHA256をchecksum一覧から探す。

receipt bodyは`schema=org.niaos.reproduction/v1`, `subject`, `release_sha256`, `policy_sha256`, `rebuilder`, `domain`, `key_id`, `issued`, `expires`, `observed_sha256`, `method=rebuild-official-binary`。署名対象はUTF-8 canonical JSONの前に`NiaOS/reproduction/v1`とNULを付けたbyte列。envelopeはbodyとbase64 signature。key registryは公開鍵hex、principal、domain、revoked、valid_from、valid_until。最低2つの独立principal/domainを要求する。製品独自の署名feedはまだ存在しない。公開Debian dashboardから署名を捏造しない。

## Strict subset and limits
ar2.0で`debian-binary/control.tar*/data.tar*`の3memberだけ。gz/xz/単一zstd frame/非圧縮tarを受理。多段連結frame/辞書/未知長zstd/sparse/未知PAX metadata/device/FIFO等は未対応で拒否。DEBは512MiB、control展開16MiB、data展開512MiB、単一file256MiB、tar項目131072の上限。JSON重複key、float、NaNを拒否。空白、文字数、extension、arch等の制約は実装参照。現実の全Debian corpus対応は主張しない。容量超過は不正とは限らずunsupportedとなるが、実行許可にはならない。

## Failure semantics
読み取りの前後に対象inode/size/mtime/ctimeを比較する。これは悪意あるkernel/rootを防ぐ証明ではない。出力は同一dirの0600一時file→fsync→上書きなしpublish→directory fsync。publish後のI/O失敗では結果不明を保持して内容を確認する。工具が正しいことと、root実行器が出力の意味を再検査することは別の責任である。
