# パッケージ形式とNiaカタログの対応

> 保存した独自カタログ研究モデルの文書です。Debian 13の実配布方針は[現在の設計判断](decisions/0001-debian13.ja.md)を参照してください。この文書の機能が実イメージへ接続済みであるとは扱いません。

## 選定の意味
DEBを採用するのは「RPMよりmetadataが多い」ためではない。RPMのfile-centricなheaderは優れている。一方、Niaは元の管理DBを保持しないので、配布物の認証と必要な属性の取得を分離できる。形式より、正確な元byteと意味の変換を検査できるかを重視した。

| 対象 | RPM | DEB | Niaでの扱い |
|---|---|---|---|
| Identity | Name/Epoch/Version/Release/Arch | Package/Version/Architecture、Source | digestが一次identity、native versionは各adapter |
| Dependency | Provides/Requires/Conflicts/Obsoletes、rich条件、phase flags | Depends/Pre-Depends/Conflicts/Breaks/Provides、Multi-Arch | native意味からconstraint/actionを作り、元metadataでも再検査 |
| Files | Headerにdigests/flags/attrs/capabilities等 | data.tarのmode/UID/GID/linkとcontrol | archive認証→payload SHA256/attrs→Nia catalog |
| Config | config/noreplace flags | conffiles、md5sums等 | 旧既定値/intent/新既定値、native validator、生成物とruntimeを別に検査 |
| Scripts | transaction scriptlets/file triggers等 | maintainer scripts/debconf/triggers | そのままroot実行しない。全必要効果をreviewed契約で実現 |
| Source | source RPMなど | Sources/.dsc/source files、Built-Using/Static-Built-Using | 保持義務・license・静的取り込みをruntime dependencyと分離 |
| Rebuild | distroごとのbuildinfo/repro資産 | .buildinfoと公式DEB再構築資産 | byte一致と独立証拠。署名済みだから再現済みとはしない |

## 注意する差異
RPM owner/groupは名前を含むmetadataにより解決される。DEB tarの数値IDを別OSの既存IDへ機械的に上書きしてはならない。Nia identity registry、元サービスの期待、データ所有者を一つの契約で照合する。file capabilityやMACの適用など、tarだけで分からない効果は除外せず契約を要求する。

DEBでDependsが成立する必要のある段階と、Pre-Dependsの展開前条件は違う。BreaksとConflictsはcoexistenceとconfigurationの許容範囲が違う。Niaはdpkg途中状態をAPI互換で再現する必要はないが、どの要求を置換したかに根拠が必要。最終的に両方installedだからよい、とはしない。

Replacesは必要なファイル所有権移動を表すが、署名されていれば任意pathを上書きできる権限ではない。Niaの移管計画・保護対象・競合writer・旧data・認可を別に評価する。libsolvが解決したReplaces/Obsoletesを自動承認にしない。

Essential/Protectedの暗黙環境、共有ライブラリABI、triggers、ユーザー作成、alternatives、diversions、initramfs、plugin cachesを解析可能な入力へ含める。未知のcontrol fieldを捨てない。今回のstrict readerが分類できないものはcatalogに残し、effects_closed=falseを維持する。

## 認証する層
Debianの通常の配信はInRelease署名→Packagesハッシュ→DEBハッシュ。このchainを検査するためにAPTをホストの管理器として残す必要はない。RPM個別署名があることも、repo freshness、組合せ、実際の設定の安全性を代替しない。

Nia派生物（os-release、設定、UKI等）と元の再現済みDEBを区別する。元を変更したDEBやrootを同一artifactとして再利用せず、旧/新digestと派生理由を保持する。独自componentの実バイナリからELF interpreter/NEEDEDと効果依存を導出し、ビルドされていないのにruntime dependencies完成と表示しない。

## 一次資料
https://rpm.org/docs/4.20.x/manual/tags.html
https://www.debian.org/doc/debian-policy/ch-relationships.html
https://www.debian.org/doc/debian-policy/ch-maintainerscripts.html
https://manpages.debian.org/unstable/dpkg-dev/deb-control.5.en.html
https://manpages.debian.org/unstable/dpkg-dev/deb-buildinfo.5.en.html
https://manpages.debian.org/unstable/apt/apt-secure.8.en.html
