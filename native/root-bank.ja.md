# 非公開rootの永続準備bank

`root_bank.py`は非公開世代を実ファイルへ展開する内部の特権サービスである。
既存catalogやaccepted rootを更新せず、導入済みpackageの第二DBも作らない。
この実装だけでは本番の世代認可・供給検査・公開・起動に接続していない。

## 保護された設定と接続

socket activationのFD 3にAF_UNIX/SOCK_SEQPACKET listenerを渡し、
`python3 -I /保護された配置/root_bank.py --config /保護された設定.json`で起動する。
実UID/実効UIDは0、LISTEN_PIDは本人、LISTEN_FDSは1を必須とする。
公開管理コマンドの代替入口ではない。製品のservice unit・専用account・mount・policyの配備は別工程である。

設定はroot所有・0600・単一linkの通常JSON fileで、重複keyや4,096 byte超を拒否する。
必須keyはversion（整数1）、bank/reservation/worker（絶対path）、client_uid（正の整数）。
client_uidは世代準備権を持つ専用の内部core accountであり、一般desktop利用者を指定しない。
workerはroot所有でgroup/other書込不可の配置を使い、開いたinodeを保持して実行する。
実行対象fileのSHA-256を結果へ記録するが、共有libraryやscript参照先の供給認証を代行しない。

bankはroot所有0700、nodev/nosuid/noexecの専用mountに置く。
`provision_bank()`は明示的bootstrapだけのAPIで、空領域へbank.jsonとbank.lockを作りfsyncする。
通常起動は両方を必須とし、欠損を自動初期化しない。bank.lockの排他flockはサービスの全生存期間保持する。
reservationはcore所有0600・単一link・長さ0の既存CAS lockで、そのinodeをサービス起動時に固定する。
lockの再作成や別inodeへの移行は、処理を停止して行う独立した復旧操作を要する。

## 依頼と実行

SO_PEERCREDの実UIDが設定と一致する接続だけ受け付ける。拒否された接続は応答前に切れる場合がある。
wireはASCIIのcanonical JSON（key順、空白なし、末尾LF）、最大4,096 byteの単一packet。
prepare依頼のkeyはversion、stage（非zeroの小文字hex32桁）、generation/root_manifest/archive
（非zeroの小文字hex64桁）、size、entries、deadline_ms。整数型・workerと共通の上限を検査する。
SCM_RIGHTSには読取専用tar FDとO_RDWRの実CAS予約FDの二つを付ける。余分なFDや切詰めを拒否する。

受け取った予約のinode・所有者・mode・長さ・access modeを検査し、排他flockを保持する。
同じopen file descriptionをworkerまで引き継ぎ、サービス側からLOCK_UNしない。
これは予約の保持であり、予約前に行うべきsite認可を証明するものではない。
信頼されたcallerは同じ予約内でNIAGEN05/NIAROOT1、catalog/closure、元DEB、論理所有権、
供給とsite効果契約を検査し、その結果から依頼とtar FDを導出しなければならない。
本番SDKのこのadapterと呼出し後の再検査は未接続である。

stage directoryを新規作成してbankをfsyncし、intent.jsonを排他的に作成・fsyncしてから
空rootを作りworkerを起動する。既存stageは上書きしない。workerには有限の期限と三つのFDを渡す。
終了code、stdoutの全結果、stderrを照合し、intentのhash、実行fileのhash、終了codeを含む
result.jsonを排他的に保存・fsyncする。成功状態はextractedまでで、publishedとeffects_appliedはfalse。
worker自身も全入力と実inode/内容を読み戻してsyncfsする。

## 再起動・障害の意味

FDを付けない`{"inspect":"stageの32桁hex"}`は保持した履歴を返す。
記録の所有者・mode・link数・サイズ・型・intent hashを検査する。完全に書かれた記録を
process停止後に読む際はfileと親をfsyncする。欠損・破損を新しい空状態に戻さない。
intentがありresultがない場合はinterruptedとなり、部分treeを再利用しない。
応答切断・期限・記録失敗は結果不確定となり、callerがinspectして判断する。
保存済みextractedは過去の結果であり、再起動後の物理rootを再検証した結果ではない。
inspectは常にphysical_revalidation:falseを返す。これを公開やbootの許可に使わない。

容量予約・独立認可/供給provider・再検証と回収・全DEB効果・公開と実boot・完全置換ISOは未完。
小さいfixtureのfsync成功とprocessのSIGKILL試験を物理電断や全filesystemの認定と呼ばない。

## 変更境界の確認

`make native-bank-check WORKER_TEST_BASE=<使い捨てVMの専用mount>`は実UIDとSCM_RIGHTS、
worker、呼出し元の予約維持、別予約の拒否、既存stage拒否、再起動後の記録を確認する。
serviceのintent記録後に所有するprocessを停止・強制終了し、成功を推定しないことも確認する。
通常のhost実行用unit testではなく、VMと外側cgroupの制限内で逐次実行する。
