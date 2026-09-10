# 共通の認証済み供給取得

`repository.py`はDebian 13のpython-tufを使用し、通常成果物・緊急修正・対応ソース・
効果契約を同じ供給経路で取得する。これは供給の信頼キャッシュであり、導入済み
パッケージのDBや特権ファイル実行器ではない。

上流の公開`Updater` APIへ、roleの署名・threshold・委譲・期限・metadata版の検査を
任せる。独自の署名方式を追加せず、上流コードにも変更を加えない。
参照: [TUF client API](https://theupdateframework.readthedocs.io/en/v5.1.0/api/tuf.ngclient.updater.html)、
[仕様](https://theupdateframework.github.io/specification/)。
Debianパッケージpython3-tuf 5.1.0-2、securesystemslib 1.2.0-2で検証する。

## 信頼と永続化

新規キャッシュの初期化はinstaller/provisioning側の内部APIに限定する。
独立に与えられたroot SHA-256と原本の一致、root署名を検査する。
本番root・鍵・URLの既定値や人工試験鍵は製品へ組み込まない。
既存キャッシュの欠落・破損を検出したら止まり、初期rootへの自動復帰を行わない。

キャッシュの所有者は実行主体で、ディレクトリは非公開、ファイルは他者にアクセスを
許さない。親を含むsymlinkと、キャッシュ内のhardlinkを拒否する。
`writer.lock`を排他的に保持し、途中でlockのinodeが変われば処理を止める。
通常成果物と緊急修正でこのキャッシュを共用し、別の信頼DBを作らない。

python-tufが更新する複数のroleファイルは、毎回private stagingへ読み込む。
検証済みroleの原本バイト列をbase64で保持した一つの`checkpoint.json`にまとめ、
一時ファイルのfsync、atomic replace、ディレクトリのfsyncの順で公開する。
鍵交代に伴う複数ファイルの削除・更新が途中で停止しても、正本は旧又は新の
完全なチェックポイントとなる。取得したtargetを返す前に公開を完了する。
変更のないcheckpointは再公開しない。

失敗したsessionは再利用しない。再度lockを取得して正本を読み直す。
途中の`.cache-tmp-<ID>`は正本から参照されないため、次回lock取得後に処分できる。
fsyncが失敗した操作を成功として返さない。ただしreplace後の同期失敗では新しい
正本が存在し得る。試験によるI/O障害注入と、実ストレージの電源断認定は区別する。

このキャッシュとroot policyは信頼状態である。OS rollbackと一緒に古い状態へ戻しては
ならない。外部の永続trust floor・時刻観測・復旧bootstrapとの接続と、本番鍵の運用は
未完である。TUF署名検査だけでこれらを解決したとは扱わない。

## 取得と緊急修正

`revalidate_target(path, raw)`は既存sessionが保持するcheckpointを一時領域へコピーし、
新しい上流Updaterで署名・版・委譲・期限・target bytesを再検証する。追加ネットワーク取得はなく、
現在のrootを使い、初期rootへ戻さない。委譲metadataは保持原本だけを返す取得器へ渡し、
探索で使用したroleを記録する。上流の私有trust状態は参照しない。
成功時は使用したroleと四つのtop-level roleの最短期限を返す。
永続checkpointとrepository identity、排他予約を前後で照合し、期限到達・時計逆行・
session期限・共通要求枠超過で失敗する。失敗sessionは再利用できない。
この検査は取得後に時間がかかる原本認証向けであり、最新remote metadataの取得ではない。

HTTPSの接続先を設定されたmetadata/target baseに限定し、redirect、資格情報付きURL、
環境変数由来のproxy、HTTP content encodingを使用しない。TLSは証明書を検証する。
ASCIIの正規化されたtarget pathに限定し、`..`やURL escapeを拒否する。
接続・読取timeoutは各5秒、要求数256、転送320 MiB、session 120秒に制限する。
metadataには別途TUF側の上限がある。DNS解決を含む厳密な実時間の上限は、
配布時のservice supervisorでも保証する必要がある。

`interim_intake.py`は、元DEBを格納した成果物全体を認証してから、期限・security epochと
各参照ハッシュを検査する。参照の供給パスは以下のとおり。

| 対象 | パス |
| --- | --- |
| 対応ソースmanifest | `sources/<SHA256>.json` |
| 効果契約 | `contracts/effects/<SHA256>.json` |
| 復旧契約 | `contracts/rollback/<SHA256>.json` |

各参照もTUFの署名・委譲と完全一致するバイト列として取得する。
成果物だけが署名済みでも、参照が欠けている・異なる場合は失敗する。
契約のバイト列認証は、その意味・副作用・復旧可能性の検証ではない。
Debian原本のarchive署名chain、実機の現在版、同じcatalogのhold、実行許可は別の検査である。

公開入口は`emgr_download_ifix -L URL [-P DIRECTORY]`。既定の出力ディレクトリは
`/tmp/ifix_<PID>`。設定された論理target URLからnative `.epkg`を取得し、原本を新規保存する。
原子的に公開する前にroot所有の`/etc/nia/repository.json`を再読し、policy変更があれば拒否する。
取得済みファイルを上書きせず、取得をインストールとして扱わない。
表示文言の参照環境との完全な適合は未受入である。

policyは`schema=org.niaos.repository-policy/v1`、絶対`cache`パス、
`bootstrap_sha256`、末尾`/`を持つ`metadata_url`と`targets_url`、正の`security_epoch`を持つ。
設定と初期化済みcacheの配備はinstaller/管理serviceの責任で、公開CLIから任意の
trust rootへ差し替えるオプションは設けない。

## 開発検証

`make image-check`で実署名・鍵交代・期限・委譲範囲・rollback・排他・I/O障害を試験する。
loopback HTTPSでは一時的な試験CAを使い、実TLSと署名検証、証明書不信頼、redirect、
破損を検査する。試験秘密鍵は一時領域から削除し、製品鍵にしない。
独立repositoryのCIは`native/Containerfile`でDebianのimage digest・署名付きsnapshotと
依存パッケージを固定し、試験時の外部networkを無効にする。
`check_download_cli.py`は新規の専用rootコンテナでだけ実行し、一時CAをコンテナ内の
通常の信頼ストアへ登録する。実公開コマンドを空のPATHで起動し、固定policy、HTTPS、
委譲署名、正確な出力、上書き拒否、参照不一致とpolicy権限不備を一貫して検査する。
ホストのpolicyやCAを変更する試験ではない。

導入済みcatalog、managed engine、GUI、完全置換ISOと実更新・復旧は引き続き未接続。
認証済み観測をJSONへ保存しても、別プロセスはその成功フラグを実行許可として信用しない。

通常DEBについては[Debian 13原本供給](archive-supply.ja.md)で、TUF targetとして認証した
明示policyとDebian InRelease/Packages/元DEBの認証を接続した。native CASと公開計画への
実行時の束縛は未完であり、既存interim intakeの参照認証とDEB archive認証も混同しない。
