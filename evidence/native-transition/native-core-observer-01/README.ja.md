# native CAS予約を保持する実observer接続

対象subject: `e14684a7a7a689fb3071ed2e0bd8ef55e26a9cf554e4aa4ec22213d041320917`。
仕様はdistribution/native/native-core-observer.ja.md、判断ADR-0093。

非root内部SDKを追加した。CASの保持原本を実配布observerへ渡し、kernel senderとsealed応答、
独立署名・scope・全原本・現在時刻を検査して、同じStoreへreceipt/policyを保存する。
通信中も予約を保持し、失敗時は両出力を消す。未参照objectやTUF checkpoint進行は残り得る。

## 実行結果

- Debian 13のGNAT14/C実compile・linkが成功した。工具版はbuild-toolchain.txt。
- 標準境界mainは最終driverで25 assertionが成功した。閉鎖Store、期限、NUL、UID、
  保持原本欠損、出力消去、同じ予約FDと競合writer拒否を扱う。
- UTF-8/path/JSONエスケープ、不正入力、C出力全消去はASan/UBSan付きで成功した。
- 最終vm-native-observer-02は13 case、test/QEMU exitとも0。
  専用core UID999から実systemd observer UID986を呼び、標準HTTPSFetcher、実TLS/TUF/OpenPGPと
  LoadCredentialを使用した。VM内一時CAであり、TLS検査の省略やfetcher差替えはない。
- 正常二要求は各50 assertionを通過し、元DEBからnative catalog/closureを作り、返却receiptを
  供給mapと保持policyへ束縛して再検証した。新規原本のreceiptを省略した計画を拒否した。
- HTTPS取得中に別FDから同じCAS lockの競合拒否を20回観測した。
  正常要求で5回/3回、別control/UID・原本・鍵の拒否要求で各3回だった。
- 別control/observer UID、非private/別所有state、改変原本、不正config、別鍵、不信頼TLSを拒否した。
  root caseはnative APIがsocket通信前に拒否する検証で、service側peer拒否の新規検証ではない。
  cache lock欠損とbootstrap再実行の拒否、不正stateの非自動修復、元inodeの保持も確認した。
- source inventory/traceability、構成/local link、lint、license表記が成功した。
  unified-auditの範囲はpass-source-structure-onlyで、形式証明や脆弱性不在の認定ではない。

362 compile入力と実workspaceを照合した。最終native driver SHA256は
`5c919b286db1c395f14e3870937561610e797e9d39da37f595dcb39f66c16692`。
65 VM sourceと全79 VM入力も照合した。input-verification.json参照。
serviceの22配布入力は前工程から不変で、既に別directory再現性を確認したDEB
`3d393d248edf558e4b6344e2dddc8db280d4cdd308a05a519396ea128bd32c6b`を再利用した。
今回のnative SDKを既存六appへ接続した配布物ではない。数学的入力は不変でproofを再実行していない。
全suiteと旧カオスcampaignも反復していない。

## 修正記録と限界

初回compileのAda演算子visibilityと、最初のVM helperで不要なPython importを先に行う問題を修正した。
最初のVMはnative要求前に停止した。最終driverには供給計画/保持policyの検証を追加し、別VMで成功した。
初回失敗・最終compile・VMログを保存し、旧入力を最終成功へ読み替えない。
CI生成時に不足していたADR登録も検査が拒否し、登録後に成功した。

本番siteの設定/鍵運用/floor/時計/installer配備、公開controllerと全managed認可への接続は未完。
人工DEB・CA/TUF/key・root contextの成功は実root admissionや世代公開を意味しない。
全DEB効果、容量/GC、実boot/復旧、完全置換ISOと全言語翻訳も未完。
root保護とhashをhardware rollback耐性にしない。

外側3 GiB/swap0/CPU1/pids128、VM2 GiB/1vCPUで逐次実行し、全job/VM停止済み。
秘密鍵、VM disk、実行ELF、DEBをGitへ含めない。私有labはnative-core-observer-01。
