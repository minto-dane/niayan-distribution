# credential署名providerの実接続受入

対象source subjectは`16a437d7542d96cb88da48788bde060b9c4c20d8a45a4601efd52b6fb343eeee`。
判断ADR-0091、配備条件は`distribution/native/archive-credential.ja.md`。
本番job/service/controllerと鍵運用は未完であり、この結果は完全置換OSの認定ではない。

## 実装と変更境界

既存TUF/OpenPGP認証後だけcredential FDを読み、独立scope/key/epoch/lifetimeを検査する
内部署名providerを実装した。read-only mountまたは完全seal済みmemfd、厳格な所有/mode/ACL、
借用FDの保持、core dump禁止・非dumpableを要求する。固定domainと署名を既存発行器で検証し、
最後のTUF再検証と時刻/期限の検査は維持する。任意message署名APIや本番の既定鍵は作らない。

既存のnative bridgeを新providerへ接続し、標準試験でもsealed memfdを使う。
private service umaskでも試験用DEBを構築できるよう、private親の下のDEBIAN directoryに0755を明示した。
上流ソース、共有API/vendor、Ada実装、永続形式、公開管理コマンドには変更がない。

## 成功した検証

- 最終Python credential 10試験と既存receipt 13試験。新しいACL拒否には別UID、group/otherの
  read許可、追加entry、ACL欠損を含む。原本認証失敗時の鍵非読取とFDの後始末も確認した。
- 現在のpkgcore commit `9de3fe6542f9cf497434855de17af602f998165e`に一致する既存private sourceで
  `run_archive_supply_tests`をcompile/link。358個のproject/compile入力を現行sourceと照合した。
  driver hashは`60cb7028edf3032bf31ef3edbe4d2032a1faac56d1115c01983fc43a469c1f93`。
- hostの実TUF/OpenPGP → credential署名 → native CASで五つのbridge判定が成功。
  正常原本の31 assertion、別key・scope・control・破損receiptの期待した拒否を確認した。
- `vm-credential-05`で実systemd 257.13のLoadCredentialをUID999へ渡した。
  root:root所有0440、正確なservice UIDへのPOSIX ACLとread-only mountを実観測した。
  同じ五bridge判定/正常31 assertionに加え、別public key、31-byte credential、欠損の三場合を拒否した。
  全serviceはinactive/failedで停止し、VM exitとQEMU exitはともに0。
- traceability/source inventory、構成とlocal link、lint、BSD-3-Clause表記の検査が成功した。
  `unified-audit`の成功範囲はsource structureであり、正式なセキュリティ監査や形式証明ではない。

最終61 Python入力、native driver、74 VM入力を記録した。`input-verification.json`と
`compile-inputs.json`、`source-inputs.json`、`vm-inputs.json`に照合対象がある。
DEB依存は検証用Debian13 APT索引から取得して使い捨てVMだけへ導入した。
実導入版は`vm-credential-05/installed-packages.txt`、バイト列はVM入力manifestで固定する。
ホストでの最初の9試験とbridge結果は初版の結果として残し、最終10試験と区別している。

## 初回失敗と修正

初回二VMはumask0077で生成したDEBIAN directoryが0700となり、dpkg-debが拒否した。
実際のsystemd credentialがservice所有0400ではなくroot所有ACL形式であることも観測した。
実形式を厳密に扱い、DEB fixtureだけ必要modeを明示して、service保護を弱めずに修正した。
三回目は正常終了oneshotのInvocationIDが保持されずログ取得が空になったため、journal cursorを使った。
四回目は正常終了後にunitがunloadされ、不要なreset-failedが失敗したため、failed時だけ呼ぶようにした。
五回目に正常系と三拒否を最後まで受入した。最初の四試行のログ/exitを保持し、成功に数えていない。

## 残る範囲と実行環境

TUF transportと原本、鍵は実署名を使う人工fixtureであり、実HTTPS配備や本番鍵運用ではない。
read-only flagはcredential由来や全alias不在の証明ではなく、Python秘密情報の完全消去も保証しない。
本番の独立設定/job/service packaging、鍵更新/失効、site floor/時刻、controller/全managed認可、
全DEB効果と実boot/復旧、完全置換ISOと全言語翻訳は別の残作業である。

外側3 GiB/swap0/CPU1相当/pids128、VM2 GiB/1vCPU。試験serviceは512 MiB/swap0/CPU1/32 tasks/90秒。
重い工程は逐次実行し、全VM/jobは停止済み。不変の全suite・全形式証明・旧カオスは繰り返していない。
私有labは`native-archive-credential-01`。秘密鍵、VM disk、library、DEBをGitへ入れない。
