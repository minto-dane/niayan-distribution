# native世代から実root準備への接続

対象subjectは`c4fe763e91ee4f77ed90a625feb04d34d2f42079da7aa850876d90fb8d26d489`。仕様は[root-preparation.ja.md](../../../native/root-preparation.ja.md)。
Prepare_Rootが世代/root/CASの予約を保持し、保持内容と現在認可を送信前後に確認する。
実tarと実予約FDをroot所有のUnix seqpacketサービスへ渡し、全応答と期待worker hashを照合する。

最終実行はvm-prepare-03/。元の人工DEBからcatalog・所有権・tar・v5世代を作り、実サービスと
workerを通して13 entryをext4上へ展開した。正常場合と展開後認可拒否を独立した空bankで確認し、
各207 assertionが成功。後者はworkerが正常終了してもSDKはIndeterminateを返した。
保存intentの世代hash・root manifest・stage・tar hash/sizeを実native生成物と独立に照合した。
認可と署名鍵はfixture専用で、本番providerの配備ではない。

固定SDKで二つのAda mainとC境界をcompile。依存profileの正規再生成後の新規checkoutでも
両binaryが完全一致したため、同じbinaryで成功した旧世代処理1,211 assertionを繰り返さなかった。
実UID0の二つのmainは5/1,132 assertionで成功した。そのうちSDK拒否は4+5の場合であり、
その他のfixture準備検査も含めた総数と区別する。全75 mainの新規受入ではない。
共有APIの追加に伴う依存profile・公開fixtureを正規工具で再生成し、17工程の整合性確認に成功。
これは新たな形式証明や全コンポーネントの実行認定ではない。

実行入力778個は元repoとコピーで全一致。binary・固定SDKのloader/libraryのhashはreport.jsonへ保持。
VMのworker_sha256は固定loaderを呼ぶroot所有launcherのhashで、C binaryのhashとは別である。
外側3 GiB/swap0/CPU1/pids128、VM2 GiB/1 vCPU、read-only基準を使う新規qcow2差分を維持。
guest/QEMUの終了は0。物理電断・抽出rootの起動・実機受入は行っていない。
秘密鍵、VM disk、runtime全量はGitへ入れない。

初回二回は保存用境界fixtureの展開が失敗した。workerはentry6の属性不一致を拒否しており、
通常symlinkにmode0644を指定した人工入力が原因だった。UID最大値も含む原本保存fixtureのbytesは
維持し、別のLinux復元可能なfixtureをgeneratorから作った。照合条件や上流DEBは改変していない。
初回の診断不足を補い、root所有のworker.jsonへ有界の終了code/stdout/stderrを記録した。
診断ログをterminal成功記録としては扱わない。初回全入力snapshotを保持したとは主張しない。

本番service/account/policy配置、独立認可/供給provider、容量予約、物理再検証/回収、
全DEB効果、実boot、完全置換ISOと全言語翻訳は未完。変更に無関係な全suite・旧カオス・
性能campaignの追加実行はしていない。
