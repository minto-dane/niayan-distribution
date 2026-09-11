# 保持したnative世代から実展開への接続

`Pkg_Generation_Stage.Prepare_Root`はNIAGEN05/06の検証済み世代を内部root準備サービスへ渡す。
単独のtar hashやサービス応答を公開認可にせず、既存のmandatory Authorizeを使う。
service/account/設定の配布物は[service-deployment.ja.md](service-deployment.ja.md)を参照。
製品の認可provider・installer/controller・公開コマンド・bootとの接続は別に必要である。

## 呼出しの順序

1. 有限期限と非特権callerを確認し、Verify_And_Holdで世代の全実体・journal・保持閉包を検査する。
   世代lockとroot lockを保持する。root archiveを持つv5、または設定済みrootを明示的に束縛するv6を受け付ける。
2. CASを再予約してmanifest pinと全保持内容・元DEB・論理所有権を再検証する。
   `stage:prepare-root`で、同じmanifest/stage/transaction/epoch/fenceの現在認可を確認する。
3. 同じCAS内のNIAROOT1/2（v5）またはNIACRT01（v6）からtar hash・サイズ・entry数を読み、
   hash検査済みの読取専用FDを開く。v6のroot_manifestは設定済みNIACRT01のdigestである。
   受渡し直前にも`stage:prepare-root`を呼ぶ。CASの実予約FDとtar FDをSCM_RIGHTSで渡す。
4. 応答後も三つの予約を保持し、manifest binding・pin・全保持内容を再読し、
   `stage:root-prepared`で現在認可と期限を再確認する。その後に予約を解放する。

v6では保存閉包の検査と、独立source providerから借用した現在のrootでのVerify_Currentも必須である。
応答後にも再観測する。providerは操作全体にわたるsource排他を保持し、既定providerは拒否する。
既存Verify_And_HoldのCAS解放契約とv1..v5のwireは変更しない。
新経路だけがCASを再取得し、その後の全工程を同じ予約で行う。
MC_Store.Native_Reservationは内部の借用FDを返すAPIであり、閉鎖・解錠・書込を許可しない。
共有契約の正本で追加し、既存の生成工具でvendorと依存profileを更新する。
fingerprintの変更を古いpolicyや過去の受入への自動互換性として扱わない。

## 通信と結果

`Pkg_Root_Preparation`と小さいC境界が、明示された絶対pathのUnix seqpacketへ接続する。
SO_PEERCREDでサービスのUID0を確認してからFDを渡す。pathだけを相手の認証にしない。
非blocking socketとCLOCK_BOOTTIMEの有限期限を使い、再接続・再送はしない。
callerがpolicyから与える期待worker hashを使い、intent hashを含むcanonical JSONの全応答と一致させる。
不足・過剰・切詰め・余分なFD・不一致応答を成功とせず、受信した余分なFDは閉じる。
借用した元FDを閉じたり、共有flockをLOCK_UNしたりしない。

戻り値OKは非公開rootのextractedまで。accepted root、導入済みcatalog、boot選択を書き換えない。
受渡し後の通信失敗・内容変化・期限・認可拒否はIndeterminateとなり、既に完成した非公開rootが
残っている可能性も保持する。盲目的に同じstageを再実行せず、bankのinspectと別の復旧判断を要する。
bankの過去結果を読むだけでは物理再検証や公開許可にならない。

## 確認範囲

更新した二つのAda mainを固定SDKでcompileし、既存の世代処理を回帰確認する。
使い捨てVMでは元DEB fixtureからnative catalog・所有権・root tar・v5世代を構築し、
同じAda経路から実サービスとworkerへ接続する。通常成功と展開後認可拒否を別の空bankで確認する。
試験の認可と供給鍵は明示した人工fixture用であり、本番providerとして配備しない。

製品installer/controller、独立認可/供給policy、容量予約、物理再検証/回収、全DEB効果、実boot、
完全置換ISOは未完。変更のないアルゴリズムの全証明・旧カオス・性能campaignは繰り返さない。

初回の原本保存用fixtureには、Linuxで通常復元できないsymlink mode 0644とUID最大値を含んだ。
これは元tarを損失なく保存する試験で、実展開の成功条件ではない。元fixtureのbytesは維持し、
別のroot-preparation fixtureをgeneratorから作る。Linuxのsymlink権限は通常0777であり、
[symlink(7)](https://man7.org/linux/man-pages/man7/symlink.7.html)、
[chown(2)](https://man7.org/linux/man-pages/man2/chown.2.html)の所有者-1の意味にも従う。
workerの属性照合を緩めたり、上流DEBを書き換えて配備したりしない。

設定済み世代のVM試験は`worker/check_root_preparation.py --configured`を使う。
同じmainが実構築・stage/engineの再予約・inspectionを行い、現在の空local設定とvendor退避を
実workerで展開する。Python側も世代wire、保存recordとscope、送信した出力digest、展開内容、
設定元の内容保持と退避先非作成を照合する。展開後の認可拒否でも非公開bankのextracted状態を保持する。
このfixture用providerと鍵を本番adapterとして配備しない。
