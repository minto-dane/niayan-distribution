# Nia OS distribution workspace

現行の単一製品は`profiles/nia-os.json`。Debian 14 Forkyの固定DEB/sourceスナップショットを入力にする。

読む順序: [選定](docs/base-decision.ja.md) → [全体構成](docs/architecture.ja.md) → [所有権と効果](docs/ownership-and-effects.ja.md) → [ストレージ/起動](docs/storage-boot.ja.md) → [組立て](docs/build-release.ja.md)。

`tools/`は非特権オフライン検査・組立て準備、`contracts/`は配置と出荷条件、`rootfs/`は秘密を含まない第一当事者identity素材である。installerや起動可能イメージではない。

`history/leap16/`は明示的な過去資料で、現行CLIから読み込まない。RPMのmetadata機能を全否定して削除したのではなく、単一Nia製品の実行経路から分離した。
