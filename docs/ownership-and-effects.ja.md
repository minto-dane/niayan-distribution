# Nia所有権・元形式・副作用契約

> 保存した独自カタログ研究モデルの文書です。Debian 13の実配布方針は[現在の設計判断](decisions/0001-debian13.ja.md)を参照してください。この文書の機能が実イメージへ接続済みであるとは扱いません。

## 設計変更

新規Niaインストールの唯一のホストpackage/catalog writerはNiaである。既存Debian/Leapからのインプレース移行は初期製品の目標ではない。native RPMDB/dpkg DBの二重書き込みや、Zypperからの管理引き継ぎは「未実装の必須要件」ではなく対象外に変更した。

ビルド室のdpkg-deb/gpgvは読み取り・組立て補助であり、対象ホストの管理権威ではない。外部ツールを使用した試験と、そのツールを稼働ホストへ残すことは別である。

## 維持すべき実行時条件

バイナリを使う以上、ELF interpreter、NEEDED/SONAME、symbol ABI、plugin検索規則、データ形式、UID/GID、サービス準備条件を無視できない。管理器互換性を捨てることは、これらの条件やライセンスを捨てることではない。

dpkgに依存するプログラムを入れる場合、依存を単純に削除して解決したことにしない。必要機能をNia契約で提供する、対象ソフトを変更して自分でビルドする、又は対象集合から外す。ネイティブ管理器を秘密の第二writerとして起動する回避策はない。

## 状態の正本

| 領域 | 正本・権威 |
|---|---|
| ソフトウェア所有権・版・属性・導入理由 | Nia catalog。root世代に所属 |
| システム変更の意図・操作ID・結果不明 | controlcoreの永続WAL |
| 管理者設定の意図・スキーマ・生成依存 | configcore。対象catalog/設定ダイジェストに束縛 |
| プロセス実行個体 | systemd。クラスタ所有権を決定しない |
| クラスタでの実行権 | site cluster authority。etcd quorumだけでデータI/O fencingを代替しない |
| 信頼・失効・受入世代 | assuranceと独立アンカー。root rollbackから独立 |
| 業務データ | 業務DB/データ管理器。catalogの復旧では巻き戻さない |

## ネイティブ形式は入力言語

DEB control/source/relationships/conffiles/data.tarの意味を独立に解釈し、中立モデルへ落とす。RPM用ソースは退行試験・研究資産として残すが、現行Nia供給プロファイルでは選べない。resolvercoreのBoolean・所有権・操作モデルは変更しない。

元DEB、抽出観測、Nia派生成果物を区別する。`/usr/lib/os-release`等をNia用に変えたrootを、元Debian DEBそのものの再現ビルド結果と呼ばない。原本DEBのハッシュは保持し、派生差分は正確な元/先のハッシュ・理由・承認を持つ第一当事者artifactにする。

## 全scriptを実行する互換性は目標にしない

preinst/postinst/prerm/postrm、debconf config、triggersをすべて記録するが、任意のシェルをrootで実行しない。旧/新版のフック、既存パッケージのtrigger、暗黙のEssential環境まで含めて、必要な結果をレビュー済み効果契約へ置き換える。

効果は、ユーザー/グループ、alternatives/diversions、ld cache、initramfs、unit reload、MAC policy、schema migrationなどを明示した操作とする。所有者、入力閉包、旧/新版に対する前後条件、冪等操作ID、永続化、逆操作又は前進復旧、停止範囲、診断情報、秘密の扱いを定義する。

スクリプトが無いことも、副作用が無い証拠ではない。他のinstalled triggerや生成物が関係し得る。現在のreaderはすべてのartifactに効果契約の必要性を残す。ダッシュボードや人工的な`verified=true`でこの条件を埋めない。

## DEB phaseとNia phase

DependsとPre-Depends、BreaksとConflicts、Replaces、versioned Provides、Multi-Archの意味を同じBooleanへ潰さない。特にReplacesを所有権の無条件な上書き許可として使わない。

元のdpkgの途中状態を完全互換で再現することは製品目標ではない。しかし元の要求を緩める変換は、バイナリとレビュー済み効果が必要条件を満たす根拠を持たなければならない。Niaの段階は取得、隔離staging、消費者の静止、管理下ファイルへの反映、意味検査/生成、サービス反映、独立した正常観測、承認である。

現在の中立resolverのInstalled bitだけではunpackedとconfiguredを区別できない。今回のDEB matcherと候補catalogは**最終集合の検査**であり、全phase/scheduleの証明ではない。段階契約を伴わない候補をexecutionへ渡さない。この境界を残したまま「全DEB対応済み」とはしない。

## 現在の実装

`debian_archive_auth.py`は実gpgvとSHA-256鎖で原本を検査し、`deb_archive.py`はホストへ展開せず属性を観測する。`nia_catalog.py`はNia所有権候補を生成する。`Pkg_Deb_Versions`/`Pkg_Deb_Semantics`は独立したSPARKソースである。

`Pkg_Root_Archive`は全pathの採用元を明示して、元DEBの属性を含む実payload spanを一つの
tarとNIAROOT1へ組み立てる。[仕様と本番接続の境界](../native/root-archive.ja.md)を参照。
構造検査はReplacesやsite policyによる所有権変更の認可を代行しない。

候補catalogを管理下rootと一つの復旧protocolで確定するwriter、全effect handler、
特権分離されたroot展開とboot接続は未完了。既存file engineの`/`拒否は二重管理互換性のためではなく、ホスト全体の資格化が終わっていないため維持する。

一次資料: https://www.debian.org/doc/debian-policy/ch-maintainerscripts.html
https://www.debian.org/doc/debian-policy/ch-relationships.html
https://www.debian.org/doc/debian-policy/ch-sharedlibs.html
