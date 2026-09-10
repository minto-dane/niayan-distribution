# Debian 13原本と共通供給ポリシーの認証

`archive_intake.py`は、既存のTUF Repositoryで認証したポリシーに従い、Debianの
InRelease → Packages → 元DEBの署名・SHA-256・サイズ・control identityを照合する。
元DEB hashとraw control hashを返し、native catalogの選択原本と比較する接続点を用意する。
導入済みDB、別writer、公開管理コマンド、署名鍵、実行許可は追加しない。

## 独立した信頼入力

TUF targetは`org.niaos.archive-supply/v1`のJSONで、`schema`、`security_epoch`、
`created_at`、`trust`だけを持つ。`trust`は`org.niaos.debian-trust/v2`である。
TUF root、取得可能なtarget/委譲範囲、独立security epoch floorと正しい時刻は
呼出側の信頼設定から与える。ミラーから得た鍵や自己申告の成功結果を信頼設定にしない。
`keyring_sha256`と`primary_fingerprints`を両方固定し、`minimum_signatures`を検査する。
OpenPGPの処理は既存の上流gpgvを使用し、ネットワーク鍵取得や上流パッチは使わない。

v2のtop-level fieldsは、上のschemaに加えて`keyring_sha256`、`primary_fingerprints`、
`minimum_signatures`、`max_age_seconds`、`future_skew_seconds`、`release`だけである。
現在時刻を署名済みJSONへ埋め込まない。内部検査APIの`now`引数へ独立に観測した時刻を渡す。
供給取得APIは実時刻を前後で読み、逆行、期限到達、単調時計で120秒以上の処理を拒否する。
DNS・gpgv・library IOを含む厳密な実時間と資源上限はservice supervisorも保証する必要がある。

`release`のfieldsは以下をすべて必須とし、未知fieldも拒否する。

| Field | 意味 |
| --- | --- |
| `codename` | trixie、trixie-updates、trixie-security、trixie-backportsのいずれか |
| `suite` | 正確なsuite。stableからoldstable等への変更も明示的policy変更を必要とする |
| `architecture` | 対象binary indexのarchitecture。all packageはこのindex内で扱う |
| `components` | 許可するcomponentの重複のない昇順list |
| `inrelease_sha256` | 認証するInRelease原本の正確なhash |
| `minimum_date` | 独立に認めるRelease日付の下限 |
| `expires` | この原本の取り込みを認める最終時刻。到達した時点で拒否 |

OriginはDebian、Labelは通常Debian、securityだけDebian-Securityを要求する。
署名が正しくても、別codename・suite・architecture・component・原本hashは受け入れない。
architecture指定は読取対象の選択であり、そのarchitectureの実OS起動認定ではない。

## 上流形式と期限

確認した[Trixie本体のRelease](https://ftp.debian.org/debian/dists/trixie/Release)には
Valid-Untilがない。この場合も署名検査を続け、独立の原本pinと期限、Dateからの最大経過時間を
要求する。最大経過時間は明示指定し、上限366日、将来時刻の許容は最大300秒である。
受理の最終時刻は、policyのexpiresとDate + max_age_secondsの早い方になる。
Valid-Untilが存在すれば必ず検証してさらに早い方を採り、空値・不正値・期限切れを無視しない。
この有限のローカル上限は、[公式の有効期限設定の説明](https://manpages.debian.org/trixie/apt/sources.list.5.en.html)も参照した。

updates、security、backportsではValid-Untilを必須とし、最大経過時間の上限は30日。
[security Release](https://security.debian.org/debian-security/dists/trixie-security/Release)では
Componentsがupdates/main等でも、SHA256表のpathはmain/...である。この対応はsecurityの
明示profileだけに適用し、一般的なpath aliasとしては受け入れない。

Releaseは大きいContentsファイルのhashも列挙する。サイズ欄の整数は有界なメタデータとして
保持し、無関係なContentsを読み込まない。実際に選んだPackages/Sourcesは従来の256 MiB以内、
元DEBや展開データも従来の読取上限を維持する。無制限な読み込みは行わない。
対応ソースは同じInReleaseのSourcesから全checksum一覧を検査し、別Releaseへの混在を拒否する。

旧v1のForky検査は過去の開発工具・比較fixture用に残す。共通native供給APIはv1を拒否する。
既存の旧開発CLIを本番管理コマンドへ転用しない。

## 返却結果と残る接続

返却前に`Repository.revalidate_target`で、保持している正確なTUF checkpointを新しい
上流Updaterへ渡し、現在時刻で署名・版・委譲・target bytesを再検証する。通常のUpdaterは
session開始時の基準時刻を使うため、取得後の同じUpdaterでの照合だけではこの検査を代替できない。
返すvalid_untilはDebian側の期限と、root/timestamp/snapshot/targetsおよび探索で使用した
委譲roleの期限の最小値とする。返却時の期限到達と時計逆行も拒否する。
同じcache予約を保持し、保存済みcheckpointのhashとrepository identityを前後で照合する。
追加ネットワーク取得、初期rootへの復帰、第二の永続cacheは行わない。未使用の委譲roleの期限は
対象へ適用しない。これは最新remote policyの取得や実行時のpolicy更新確認ではない。
sessionの期限・request/転送上限と唯一のdurable trust checkpointは既存Repositoryが管理する。
古いOS世代と一緒にtrust floorを戻さない保管、実行直前の独立policy確認は引き続き必要である。

`AuthenticatedArchive`やそのJSONは観測結果であり、他プロセスの成功フラグを信用する仕組みではない。
native CASへ取り込んだ元DEB/control hashを正確に照合し、供給認証の原本・policy・epochを
公開計画と同じ予約へ束縛するmanaged adapterは未完である。現在世代・全phase・効果契約・同意・
所有権・healthの認可も別途必要。`execution_permit`と`native_cas_bound`はfalseのまま返す。

別の[供給記録発行API](archive-receipt.ja.md)は、この実認証を行ってから正確なhashと期限へ署名し、
nativeの一原本検証へ接続する。任意の観測recordを署名するAPIではない。鍵/providerの本番配備と
全公開計画への接続は未完であり、この観測API自身のfalse flagを変更しない。

## 検証

`tests/test_debian_trust.py`は実OpenPGP署名とDEBを使い、明示pin、期限、日付floor、suite、
security component、architecture、元DEBとソースの完全照合を検査する。
`native/test_archive_intake.py`は実TUF署名も組み合わせ、どちらかの認証を省略した入力、
旧policy、epoch不足、処理中の期限・時計変化・target変更・UID0を拒否する。
`native/test_repository_revalidation.py`は保持原本の実署名を再検証し、各roleと委譲roleの期限、
鍵交代後のroot、オフライン性、checkpoint/identity/予約の変更、要求枠とsession期限を検査する。
試験依存はnative/test-packages.txtへ記載し、必須工具の欠落をskipで隠さない。
`make image-check`のnative-checkから、既存工具も含むtool-checkを実行する。
公式の公開Releaseと原本DEB/対応ソースの観測は、合成署名fixtureや本番policyの配備と区別して記録する。
