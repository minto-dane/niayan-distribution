# Debian 13上でNiaを唯一のパッケージ管理主体にする

2026-09-08。利用者がAPT等の完全置換を明示的に指示したため、
[0001](0001-debian13.ja.md)のAPT/dpkgを恒久的な正本にする選択を置き換える。
Debian 13、上流ソースの無改変、再現性、操作性、独立コンポーネント維持は継続する。

## 製品の不変条件

稼働するNiaOSの所有権・導入版・導入理由はNia catalogに一元化する。
pkgcore・resolvercore・configcore・controlcore・assuranceを、同じ排他予約と
永続トランザクションに接続する。APT/dpkgやPackageKitの別writer、別の自動更新器を
同じ管理対象へ並行接続しない。シェルからAPTを呼ぶラッパーは完全置換に数えない。

開発用Distrobox、固定ビルダー、独立比較試験でのAPT/dpkg使用は、配布先の
管理権威と別である。今回の指示を理由に開発PCのAPTを削除しない。

Debianの署名済み原本DEBと元の依存宣言を保存する。Nia用に意味を変換するときは、
版付きPre-Depends、Depends、Provides、Conflicts、Breaks、Replaces、conffiles、
triggers、ユーザー/グループ、alternatives、生成キャッシュ、initramfsを別々に扱う。
依存を満たしたことにする偽のProvides、管理器の削除を隠すcontrol改変、
未実装callbackの常時成功、任意maintainer scriptの稼働host上のroot実行は採用しない。

## 実装境界

既存の`Pkg_Managed_Engine`には、認可・静止・設定・解決・元形式再検査の必須
callbackがある。`Pkg_File_Engine`の実FD/CAS/WALと復旧処理は再利用対象であり、
新しいPython工具を第二の特権パッケージ実行器にしない。ホスト`/`を拒否する境界は、
root/catalog/effectの実接続を受入するまで保持する。

独自catalogの既存文書から所有権・副作用・失敗時の規則を引き継ぐ。
Forky由来の供給lockや未受入のUKI/XFS/HA構成を、Trixieで検証したことにはしない。
kernel/systemd/KDEの上流パッチで互換性不足を隠さない。

## 実データからの移行作業

`native/audit_transition.py`は旧ISOから取り出したstatus/controlを読み取り、
元の版付き関係を維持して管理器除外後の不足と、保持された効果ファイルを記録する。
これは実行許可や原本DEBの認証ではない。コメントを含むコマンド出現から
効果を自動承認せず、スクリプトが存在しないパッケージにも暗黙のtriggerを調べる。

元ISOには2,239パッケージがあり、1,493パッケージに計2,263の保持された
効果ファイルがある。11個の管理器関連パッケージを仮に除くと12個の元依存条件が
未充足になる。Discover、Python、音声firmwareも含まれる。全ファイル・動的起動
経路まで網羅した数字ではなく、既知の移行対象の下限である。

最初に対象集合の原本DEB認証、元形式の最終集合とphase検査、全副作用の
入力/出力/復旧契約を閉じる。次に新規root assemblerとcatalogの原子的公開を接続し、
取得・検証・stage・静止・反映・生成・health・commitの各境界で停止を注入する。
ロック欠落、容量不足、fsync失敗、結果不明、旧世代、失効した署名を拒否する。
業務データと信頼の失効世代をOS rollbackに巻き込まない。

その後、新規Nia-only ISOで導入・追加・更新・削除・再起動・復旧・セキュリティ更新を
実行し、APT/dpkgの実行ファイル・DB・timer・GUI backendが第二writerとして
残らないことを検査する。旧ISOの起動結果をこの受入へ流用しない。

## ハードニング

[専用基準](../../hardening/README.ja.md)に出典、設定値、互換性上の選択、実測範囲を残す。
ASLR/NX/RELRO等は有効値と成果物を検査する。ブラウザ・日本語入力・user namespace
など日常の操作経路を維持する。規制/ベンチマーク全体の準拠や、他OSより安全という
未測定の比較は主張しない。ハードニングは更新・復旧・権限境界の代替ではない。

## 現在の配布物

既存の`image/`・`packaging/`とISO 09はAPT/dpkgによる旧経路の検証済み基準である。
完全置換後の製品ではない。`native/`が置換工程、`hardening/`が独立に試験できる
セキュリティ基準を所有する。完成まで既存ISOの内容や過去の受入証跡を改変しない。
