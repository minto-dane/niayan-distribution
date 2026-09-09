# native検査記録を必須とする世代公開

対象source subjectは`5c4bcdd2d488b40e6cf4a2582ca5171121ff281528febda7ccfd2f971ec42b9a`。
基準root commitは`181ff42`。この証跡は合成世代の公開・復旧SDKの検証であり、
本番認可、実DEB payload適用、実root/boot、APT完全置換、全言語翻訳の完成を示さない。
集計は`report.json`、各工程の終了状態と対象入力は二つの工程reportを参照する。

`NIAGEN03` manifestは、native policy・正確な基準descriptor・候補catalog・保持閉包・
検査結果を記録する`NIAGINT1`のCAS hashを含む。Publisherは実状態と照合した基準を使い、
元DEBから初期最終集合又は通常更新を再計算して記録と照合する。既存Managed guardも必須。
仕様は`native/publication-intent.ja.md`、判断はADR-0076。
CAS予約は既存実行器へ渡す際に解放するため、公開全区間で同じCAS lockを保持するとは主張しない。

標準全体検査116工程、全登録Ada main 71本、18アプリの構築が成功した。
ホストsource検査24工程、私有D-Bus 32+10試験も成功した。
Python単体試験は582件発見、source検査では11件skip。skipは実行成功に含めない。
pkgcore単独CI 25 mainと独立readerが成功。stageは1202、公開・復旧は1638 assertions。
root拒否は専用UID0コンテナの8 driverで確認し、通常UID0利用は認めない。

独立readerは二つの公開済み検査記録の正規バイト列、policy、native結果とBindingを
元DEBから照合する。既存の16 catalog観測、18更新観測、四Binding、更新保持8欠落も維持する。
保持欠落は検査記録自身を含む73ケース。不正記録26ケースを拒否し、失敗時の返却Bindingを消去する。
構造上は正しいmanifestへ接続され、stageを完了した三候補も、結果不一致・別root・偽初期構築の
各理由で公開を拒否し、root.stateとgeneration.nextの正確な旧内容を維持する。
NIAGEN01/02の新規公開と再実行を拒否する。旧版の途中transactionは旧実装で復旧を終えてから
移行する必要がある。旧版の本番稼働環境からの移行は認定していない。

新規コピーを異なるmtime・作業パス・TZで独立構築し、pkgcoreの29実行ファイルと
全18アプリのバイト列が一致した。ELF属性も照合した。
pkgcore 731入力を四コピー、workspace 3350入力を三コピーで照合した。
全体runnerはTZ/SOURCE_DATE_EPOCHを子から除去し、独立側はPacific/Honoluluと固定epochを使う。
全7repoの数学的入力は不変なので証明を重複実行していない。変更runtimeはSPARK対象外。

別の新規コピーをASan/UBSan付きで構築し、stageと公開の同じassertionsが成功した。
計測対象はC境界とallocator/library-call interceptionであり、Ada及び上流library本体は非計測。
leak検査は無効。`reference-snapshot/`はこのsanitizer実行の最終状態を保存したもの。
独立readerの結果が通常pkgcore CIの結果と完全一致することを確認した。
snapshotには合成媒体、CAS、journalと三つの拒否候補も含む。実OSのrootではない。
再読取は保存した`readers/compare_current_catalog.py`へroot/state/cas/bank/media/native.logを指定する。

資格検査前の診断も`attempts/`に保存した。最初はWord演算子の可視性によるコンパイル失敗、
二回目は新規v3を未知形式としていた既存fixtureの失敗、三回目はByte演算子の可視性による
コンパイル失敗だった。四回目はstage 1202・公開1616成功。その後に旧版二種の拒否、追加不正記録と
期限試験を追加して、新規全体コピーで最終資格検査を実行した。診断結果を最終入力の結果に流用しない。

固定image、networkなし、JOBS=1、外側scopeのmemory 3 GiB・swap 0・CPU 1コア分・pids 128を使用。
工程は直列実行し、上限引上げやguard迂回は行っていない。新規依存・上流パッチ・共有runtime変更なし。
fixtureのtree/versionはcatalog bytesであり、全DEB phase・所有権・属性・効果の実行を証明しない。
本番供給/policy adapter、保護移行、安全なGC、実起動切替、完全置換ISOは引き続き未完である。
