# 現行配布対象: openSUSE Leap 16.0 公開配信のみ

SLES profileは履歴へ移動し受け入れない。6runtime repo + 本workspace。
[現在の選定](docs/base-selection.ja.md)。旧版のSLES対象記述は廃止判断の記録。

# SUSE系ディストリビューション組立て基盤

本版はISO/VMイメージではない。通常のmutable openSUSE Leap 16.0 / SLES 16.0を
別プロファイルとして扱う、実行可能な入力検査・KIWI記述生成工具と設計契約の束。
`configcore`を含む5独立Adaリポジトリの外に、ディストリビューション組立ての責任を分離する。

[選定調査](docs/base-selection.ja.md)、[組立て](docs/assembly.ja.md)、[移行](docs/migration.ja.md)、
[ストレージ・回復](docs/state-and-recovery.ja.md)、[残る受入条件](docs/qualification.ja.md)。

```text
profiles/      familyを混ぜない16.0の固定基盤条件
contracts/     役割、状態領域、設定adapter対象、release gates、必要パッケージの役割
schemas/       開発用入力形式の規定（本番証拠の代わりではない）
tools/         distroctl.py + repo_metadata.py (offline/build-only)
tests/         実工具の否定試験。人工データは有効なRPMではない
kiwi/          生成対象の仕様説明。キー・実RPM・起動imageは同梱しない
```

通常ホストの所有者はzypper/RPM。Mission Coreは明示した別管理rootのみ。
ホスト/とRPMDBの所有権移行を無検証で実施するインストーラhookは付けない。
SLES製品・subscription・認定・商標を自作ディストリビューションへ継承したと表示しない。
公開再配布とSLES契約に基づく内部派生を別のリリース審査にする。
