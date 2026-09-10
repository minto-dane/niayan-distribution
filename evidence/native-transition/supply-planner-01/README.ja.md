# 現在site trustから実observerと供給計画への接続

subject: `08049713239be371a3f3da7e4a01feb043aa1e78f3af3686a69a7839ce62542c`。
判断ADR-0094、製品仕様distribution/native/supply-planner.ja.md。

計画用site sessionを追加した。計画前の架空hashを不要にし、保護policy/floorのpin・時計高水位・
期限を維持して供給認証とmap/保持policyを作成する。Bind_Publicationは実際のhashへの一方向束縛である。
計画中のsessionを公開callbackへ使えない。plannerは現在siteから鍵/epoch/age/UTCを取得し、
原本認証と完全な供給計画作成の前後で再観測する。失敗では三出力を消去してsite sessionを閉じる。

## 検証

- Debian 13で変更Adaと依存Cを実compile/linkした。工具版はbuild-toolchain.txt。
- 元のobserver境界25 assertion、site形式/拒否境界248 assertionが成功した。
- 実配布observerのVM17 caseが成功し、test/QEMU exitとも0だった。
- 新しい正常計画二要求は各54 assertion。実root保護site入力とfloorからauthorityを取得し、
  実HTTPS/TUF/OpenPGP/credential → native CAS → catalog/closure → map/保持policyを検査した。
  公開用callbackへの束縛、計画/公開状態の混同拒否、zero hash束縛の拒否も確認した。
- HTTPS GETに到達した時にsite policyと対応floorを更新するcaseと、floorを削除するcaseは、
  各48 assertionで拒否を確認した。更新したtrustを途中採用せず、map/policy/untilの全消去とsession停止を確認した。
  mutation到達をhelper自身がassertするため、未実行の変更を成功と数えない。
- 元の直接observer正常二要求は各50 assertion。別control/UID・原本・state/config/key/TLS、
  root API、bootstrap再実行・cache lock欠損の既存境界も成功した。
- 通信中のCAS競合排除を合計32回観測した。新しい計画四要求は各3回で、元の経路は合計20回。
- source inventory/traceability、local link/lint、BSD-3-Clause表記が成功した。
  unified-auditはpass-source-structure-onlyであり、全脆弱性不在の認定ではない。

364 compile入力と実workspace、65 VM source、全79 VM入力を照合した。
driver SHA256は`96e08ad7f2d85c4aade56cc5e642b6a09bf4af85359ac101b6aec83d5cd45912`。
serviceの22配布入力は不変で、前工程で再現性を確認したDEB
`3d393d248edf558e4b6344e2dddc8db280d4cdd308a05a519396ea128bd32c6b`を再利用した。
新plannerを既存六appへ配布した意味ではない。詳細はinput-verification.json。
数学的入力は不変で形式証明は反復していない。無変更のC transport sanitizer、全suite、旧カオスも反復していない。

## 残る製品接続

plannerのpredecessorとBind_Publicationのhashはcaller contextである。実root.stateのadmission、
全managed guard、同意・停止barrier・効果契約・health・世代公開の許可を代替しない。
本番site設定と鍵/floor/時刻/installer、公開controller/コマンド、全DEB効果、容量/回収、
実boot/復旧、完全置換ISOと全言語翻訳は未完。VMのCA/TUF/key/DEB/root contextは人工fixtureである。
未参照CAS objectや進んだTUF checkpointは拒否後も残り得る。root所有をhardware rollback耐性にしない。

外側3 GiB/swap0/CPU1/pids128、VM2 GiB/1vCPUで逐次実行し、全VM/jobは停止済み。
秘密鍵、VM disk、DEB/ELFをGitへ含めない。私有labはnative-supply-planner-01。
