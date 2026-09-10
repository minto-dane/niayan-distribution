# 元DEB rootアーカイブ組立ての変更境界検証

対象source subject: `b873fa17bd01cd0789c2638ecc3d47200774fd358961f889d6bbf3af646736d6`。
新SDKの固定container実コンパイル、Ada131 assertion、実UID0拒否3 assertion、CI登録関連43検査が成功。
三つの人工DEB、13 path、7 entry kindを実tarへ組み立て、独立したPython読取器で全選択span、
全属性、hardlink順、manifestのclaim番号を照合した。root.tarとroot-manifest.binは実出力である。

初回はstrict compilerのpass-by-copy警告で失敗した。警告を無効化せず、既存と同じ明示Check
helperで失敗を処理してから成功した。build-01.logを保持し、run-02.logの112 assertionと
manifest不整合検査追加後のnative-final.logの131 assertionを区別する。
保持入力とroot tarの欠損・明示復元は私有CASだけで実行した。物理rootへ展開していない。

final-pkg-inputs.jsonの748ファイルは、buildコピーと元pkgcore双方を最終照合した。
source checkは仕様追記前後を区別する。最終チェックはfinal-source-check.log。
変更のない全体試験・数学的証明・C sanitizer・native image・旧カオスcampaignを繰り返していない。
全74 Ada mainは登録数であり今回実行数ではない。新binaryの全量リリース認定ではない。

再実行する場合は固定開発imageで `gprbuild -j1 -P tests.gpr run_root_archive_tests.adb`、
private mode0700の新しいstoreを用意して `build/test-bin/run_root_archive_tests STORE tests/fixtures/root-archive`
を実行する。そのlogとstoreを `tests/compare_root_archive.py` の --native/--cas に渡す。
媒体は `tests/fixtures/root-archive`。resource制限はreport.jsonを参照する。
通常のcomponent CIと統合runnerにもこのdriverと独立照合を登録した。

本番所有権・効果認可、世代保持、特権展開、実サービスとboot/復旧、完全置換ISOは未完。
仕様は [root-archive.ja.md](../../../native/root-archive.ja.md)。
