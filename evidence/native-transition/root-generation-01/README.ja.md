# rootアーカイブの世代保持・公開・復旧

最終source subject: `eebfc077554d13fbc06738c47e2ca0711f9c428cb2c8c3b7a25dcc4bf491268a`。
Pkg_Root_Archive.Verify_TargetとNIAGEN05により、元payloadの採用claimと実tarを、
既存pin・descriptor・公開計画へ束縛した。root.tar/root-manifest.bin/generation-manifest.binは
最終root driverの実成果物である。仕様は [root世代](../../../native/root-generation.ja.md)。

固定imageと3 GiB/swap0/CPU1/pids128、JOBS=1で関連三つのAda mainをbuildした。
最終実行はfinal/。root組立て/実staging196、旧stage1211、旧公開2023、新root公開142 assertion、
別の実UID0拒否4 assertionが成功した。三つの独立照合、CI登録関連43検査も通過した。
74 mainは登録数であり今回の全実行数ではない。inputs-final.jsonの752入力は
元pkgcoreと実buildコピーの双方をhash照合した。binary hashはreport.jsonを参照する。

root driverは三つの元DEB・13 path・全7種類のentryを含むtarの実stagingと世代pinを確認した。
新公開variantは一つの元DEB・10 pathを使い、root manifest/tarの公開前欠損を拒否した。
root manifestの欠損はcommit拒否後の復旧とaccepted native読取でも拒否し、明示復元後の
記録済み更新は供給期限後でも既存の現在policy/Managed guardの下で復旧した。
独立Pythonは実accepted stateからplan/descriptor/manifest/pinと実staged tarを辿って
原本spanへ照合した。final/root-publication.logには実wrapperの結果があり、私有fixtureは
wrapper終了時に削除した。initial-publication-*は検査順調整前の別実行であり、最終結果と
混同しない。両実行の公開plan・manifest・tar hashと独立検査reportは一致した。

初回のcompiler警告による失敗と、修正後の最終検査前の実行を保持した。
警告を無効化せず、テストの文字列添字を宣言された下限へ合わせた。
final/はv5のplan I/O後に期限付き原本検査を行う最終実装である。
変更のない全体suite、数学的証明、C sanitizer、native image、旧カオスcampaign、性能研究を
繰り返していない。今回の欠損操作は私有CASのみで、物理電断・SIGKILL全行程ではない。

この公開/復旧は実root.state/WALを使うが、認可・供給observerは人工fixtureである。
実OS rootへの展開・mount・boot、全効果、本番provider、typed GC、完全置換ISOは未完。
通常CIにもroot driverとcheck_root_publication.pyを登録した。既存供給・epoch/fence・
Managed guardと非特権境界を緩めていない。
