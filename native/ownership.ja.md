# 機能の管理主体と既存基盤の役割

利用者の最新指示に従い、Niaの管理機能を一つの処理系へ接続する。
パッケージ管理では、dpkgを内部バックエンドとして残す案も採用しない。
APT/dpkg/PackageKitの代替実装が未完であることを、単なる削除で隠さない。

| 管理する機能 | Nia側の担当 | 既存ソフトウェアの扱い |
| --- | --- | --- |
| 導入版・所有権・更新・緊急修正 | pkgcoreの同じcatalogとtransaction | APT/dpkg/PackageKitの別writerを置換する。完了前の既存ISOは比較用として保持 |
| 依存解決と適用順序 | resolvercoreと元DEB意味の独立検査 | 元の依存宣言と供給証拠を保持。別のAPT解決・適用経路へ委譲しない |
| 自動更新と管理画面からの更新 | 同じ管理要求と認可の入口 | unattended-upgradesやDiscoverのPackageKit経路を並行運用しない。取得だけを導入完了に数えない |
| 構成の整合性と生成物の検査 | configcore | systemd、各サービス、各キャッシュ生成器の公式設定機構を使う |
| 状態の保存と復旧 | statecore、pkgcore、controlcore | XFS、LVM、暗号化、systemdを下位の実装として使う。これらの工具自体を重複管理器と誤認しない |
| 停止・反映・健全性の判断 | controlcoreと実観測adapter | systemctl等の独立したコマンドは維持し、対象資源だけを制御 |
| 同意・アプリ権限・取消 | capsulecoreとportal/broker接続 | デスクトップportal、polkit、AppArmor等を役割ごとに接続。未接続の代わりに削除しない |
| 供給認証・失効・証跡 | assuranceと共有の信頼policy | 元Debianアーカイブの署名、TUF、TLSは異なる段階を検証する。相互の代用品にしない |

公開管理操作はinstallp等の採用したコマンド体系に統一する。別名の公開入口や、
同じ管理対象へ別の正本を書き込む経路を増やさない。内部SDKや元形式の検査器は
別の公開パッケージマネージャではない。

切替の条件は機能ごとに、実接続・権限境界・正常操作・中断復旧・呼出し元の接続を
確認すること。既存機能の削除が先行して、更新や復旧ができない状態にはしない。
管理主体の一元化は、root権限で予約を無視する任意変更まで防げるという意味ではない。

[実装と未完条件](acceptance.json)、[完全置換方針](../docs/decisions/0002-native-package-authority.ja.md)、
[管理インターフェイス](../docs/decisions/0003-management-interface.ja.md)を併せて参照する。
