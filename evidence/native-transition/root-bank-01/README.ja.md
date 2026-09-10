# 非公開rootの永続準備bank

対象source subjectは`bbd17d3d2eca6f80f7a76970b324dc2c04800889e6205f884bb139f82a0479a5`。
最終C workerは`5f7f0b32f25186d60562db6020c55311297657ac8d1a2231df99e3c855026b34`。
[永続準備bank](../../../native/root-bank.ja.md)を固定SDK由来のworkerと使い捨てVMで確認した。

最終実行はvm-bank-03/。実peer UID、SCM_RIGHTSによるtar/実CAS予約の受渡し、正常展開、
別予約/重複stageの拒否、呼出し元のflock維持、再起動後の記録読取を確認した。
意図だけを保持した人工状態と、完全なintentのbytesが見えた後の実サービスSIGKILLを区別して記録した。
両方ともinterruptedであり、公開成功を推定しなかった。SIGKILL時点でworkerが実行中だったとは認定しない。
再起動観測は保存結果の読取で、物理root再検証ではない。

同じVM実行の先頭で、更新したworkerの全7 inode kind・10 entryの属性/内容と五つの拒否場合が成功した。
guest ext4の専用bind mountはnodev/nosuid/noexec。tmpfsではないが、基準をread-onlyで参照する
新規qcow2差分diskであり、実機電断・基準全量の再認定・抽出rootの起動試験ではない。
QEMUとguest試験の終了codeは0。外側3 GiB/swap0/CPU1/pids128、guest2 GiB/1 vCPUを維持した。

report.jsonで五つの実行入力と元repoの一致を確認し、最終binaryと固定SDK共有libraryのhashを保持した。
VMは固定loaderを呼ぶroot所有の小さいlauncherを使用する。result.jsonのworker_sha256はこのlauncherで、
C binaryのhashとは区別する。launcher本文はvm-check.pyへ保持した。独立した供給認可の代用ではない。
秘密鍵・VM disk・runtime全量はGitへ含めない。SSH工具のhashはssh-tools.json。

初回二回の失敗は未許可peerへの即時切断を試験側が扱えなかったもので、ログを分離して保持した。
最終試験は未許可peerが依頼を送る前に拒否されることを確認する。保護を緩めて成功させていない。
初回入力の全snapshotは保存していないため、それらのログを最終入力の受入として使わない。

SDKの本番世代admission adapter、製品service/account/policy、容量予約、再検証/回収、
全DEB効果、実mount/boot、完全置換ISO、全言語翻訳は未完。準備bankを製品完成と呼ばない。
入力不変のAda suite・証明・旧カオス・性能campaignは繰り返していない。
