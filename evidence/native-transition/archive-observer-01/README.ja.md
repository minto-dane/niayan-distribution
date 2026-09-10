# 実配布archive observerとHTTPS/native接続

対象source subjectは`036f81116950a4937a69e969152faae3043ecfbb159868533c036cff045dc38b`。
判断ADR-0092、製品仕様は`distribution/native/archive-observer.ja.md`。
独立設定・既存cache・HTTPS・credentialとcore向けFD通信を、実配布物へ接続した。
全NiaOSのproduction認定や完全置換ISOの完成ではない。

## 実装

専用nia-supply UIDのsocket起動serviceが、nia-pkg peerから三原本FDを受ける。
保護設定、bootstrap履歴、既存TUF cacheを確認し、私有原本copyから既存のHTTPS/TUF/OpenPGP認証と
credential署名を行う。前後の設定と時刻を再検査し、供給receipt/policyをsealed read-only FDで返す。
内部clientは実senderのkernel credentials、相関ID、FD/seal/hash、署名、scope、現在時刻を確認する。
供給認証を同意・DEB効果・世代実行許可にはしない。公開管理コマンドと共有API/vendorは不変。

packageは既定pin/seed/cacheを含まず、停止状態で導入する。明示provision serviceだけが初期stateを作る。
通常serviceはStateDirectoryによる作成/chownを行わず、既存の0700・専用UID所有とbootstrap記録を要求する。
欠けたlockを再作成しない。供給checkpointは既存形式の一つだけで、第二の導入済みDBを追加しない。

## 検証結果

- 新しい設定/要求/原本copy/FD受渡し/seal/期限/後始末の単体9試験が成功した。
- `niaos-archive-observer 0.1.0 all`をDebian13の非root buildで生成し、二つの独立directoryでDEBが一致した。
  hashは`3d393d248edf558e4b6344e2dddc8db280d4cdd308a05a519396ea128bd32c6b`。
  source tar.xzと.dscも両directoryで一致した。source tarのhashは
  `45ba096add42d38bf9d57b9aeafd50bc0dc56137f9ac522af15306d4d17af3d1`。
  build依存とdescriptorはfinal/final-rebuildの.buildinfo/.dscへ保存した。
- 最終`vm-observer-02`で実DEBを導入し、package導入時の停止とcache未初期化、明示bootstrapと
  再実行拒否を確認した。systemd credentialの実senderはUID986、core clientはUID999だった。
- VM内の一時CAをOS trust storeへ配備し、標準の製品HTTPSFetcherを使った。
  fetcher差替えやTLS検証省略なしで、実TLS/TUF/OpenPGP → credential署名 → 実native CASを通過した。
  二つの連続要求はそれぞれnative31 assertionを通過した。
- 非private state、別state所有者、root peer、原本改変、未保護config、別credential、不信頼TLSを拒否した。
  不正なstate owner/modeはそのまま残り、自動修復されないことも確認した。
  cache lock欠損では起動assertionで拒否し、bootstrap記録と元lockのinodeを維持した。
  `result.json`の全11 caseが成功、test/QEMU exitはいずれも0だった。
- source inventory/traceability、source構成とlocal link、lint、BSD-3-Clause表記の整合性が成功した。
  source監査工具の成功範囲は`pass-source-structure-only`であり、全脆弱性不在や形式証明ではない。

22 package入力（11 Python moduleを含む）、65 VM Python入力、全79 VM入力をhashへ束縛した。
package-inputs.json、vm-inputs.json、input-verification.json参照。
native driverは前工程でcompileしたhash
`60cb7028edf3032bf31ef3edbe4d2032a1faac56d1115c01983fc43a469c1f93`を使った。
Ada入力は不変で、前工程の358 compile入力の記録はarchive-credential-01にある。
今回はAda再compile、全suite、形式証明、旧カオスcampaignを繰り返していない。

## 修正と限界

最初のbuild呼出はintegration rootを作業directoryにしてしまい、changelog不在で構築前に停止した。
正しいprivate輸出先で構築し、provision unitはpackage名と異なるfile名のためinstall manifestへ明示した。
最初の実VMは成功したが、通常StateDirectoryが既存状態の所有者を変更し得る設計を見直した。
通常serviceをReadWritePathsと保護検査へ変更し、二つのstate拒否を追加した最終VMで再検証した。
初回VMと旧DEBのhashも残し、最終入力での結果へ読み替えない。

TLS通信と署名は実物だが、CA/TUF root/key、DEB原本は隔離VMの人工fixtureである。
本番siteの設定・root/鍵運用、非rollback floorと時計、installerへの組込み、実coreの保持原本からの
呼出と同じCAS予約への保存、全managed認可、全DEB効果・起動切替/復旧・完全置換ISOは未完。
private stateの所有検査をhardware rollback耐性とはしない。大きな入力が資源上限で失敗する可能性も残る。

全工程は外側3 GiB/swap0/CPU1相当/pids128、VM2 GiB/1vCPUで逐次実行した。
全VM/job終了済み。私有labはnative-archive-observer-01。
秘密鍵、VM disk、library、DEB/source archiveをGitへ入れず、配布入力と検証記録を保持する。
