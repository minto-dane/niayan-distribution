# NiaOS distribution

Debian 13 Trixieから、上流コードを変更せずに構築するディストリビューション。
現在はAPT/dpkgをNiaへ完全置換し、操作性を維持したハードニングを進める。
既存ISOはAPTを使う比較基準であり、置換完了・本番認定は未実施。

読む順序: [最新の設計判断](docs/decisions/0002-native-package-authority.ja.md) →
[公開コマンドと緊急修正](docs/decisions/0003-management-interface.ja.md) →
[置換工程](native/README.ja.md) → [ハードニング](hardening/README.ja.md)。
旧基準版の[構築と試験](image/README.ja.md)は再現用に維持する。

amd64・KDEの実ISOがBIOS/UEFI/Secure Boot、日本語入力、オフライン／オンライン導入と再起動を通過した。[対象ISOと6項目の受入記録](evidence/debian13/accepted-09/README.ja.md)。同じ入力からのISO全体の再現一致と、対応ソース1,415組の収集・補完・コピー後の照合も確認した。実機や別デスクトップの受入とは区別する。

| ディレクトリ | 役割 |
| --- | --- |
| `native/` | 完全置換の実データ検査と実装工程。特権executorは未接続 |
| `hardening/` | 出典付き基準・rootfs設定・成果物/実行時/VM検査 |
| `image/` | digest・snapshotを固定したビルダー、live-build設定、パッケージ構築、VM試験 |
| `packaging/` | NiaOS識別情報・設定・メタパッケージのDebianパッケージング |
| `release/` | 完成した配布物のソース補完。ISOの生成入力とは別に記録する |
| `profiles/`・`contracts/`・従来の`tools/`・`rootfs/` | 保存したForky/独自カタログ研究モデル。実イメージには適用しない |
| `tests/` | 上記研究モデル・入力検査器の試験。ISO起動試験とは別 |
| `history/leap16/` | さらに以前の設計資料 |

従来の[構成仕様](docs/architecture.ja.md)、[所有権モデル](docs/ownership-and-effects.ja.md)、[ストレージ契約](docs/storage-boot.ja.md)は研究モデルの説明として残す。今回の配布で全て実装したという意味ではない。コンポーネントの形式検証と、実OSの起動・導入・更新・復旧の受入を別々に記録する。
