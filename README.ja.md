# NiaOS distribution

Debian 13 Trixieから、上流コードを変更せずに構築するディストリビューション。APT/dpkgをパッケージ状態の正本とし、NiaOS独自部分をDEBとして追加する。開発版であり、本番認定は未実施。

読む順序: [設計判断](docs/decisions/0001-debian13.ja.md) → [構築と試験](image/README.ja.md)。

amd64・KDEの実ISOがBIOS/UEFI/Secure Boot、日本語入力、オフライン／オンライン導入と再起動を通過した。[対象ISOと6項目の受入記録](evidence/debian13/accepted-09/README.ja.md)。実機や別デスクトップの受入とは区別する。

| ディレクトリ | 役割 |
| --- | --- |
| `image/` | digest・snapshotを固定したビルダー、live-build設定、パッケージ構築、VM試験 |
| `packaging/` | NiaOS識別情報・設定・メタパッケージのDebianパッケージング |
| `profiles/`・`contracts/`・従来の`tools/`・`rootfs/` | 保存したForky/独自カタログ研究モデル。実イメージには適用しない |
| `tests/` | 上記研究モデル・入力検査器の試験。ISO起動試験とは別 |
| `history/leap16/` | さらに以前の設計資料 |

従来の[構成仕様](docs/architecture.ja.md)、[所有権モデル](docs/ownership-and-effects.ja.md)、[ストレージ契約](docs/storage-boot.ja.md)は研究モデルの説明として残す。今回の配布で全て実装したという意味ではない。コンポーネントの形式検証と、実OSの起動・導入・更新・復旧の受入を別々に記録する。
