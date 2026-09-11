# 設定済み世代の公開と受理済み記録復旧

source subject: `ab72f448d25ce2e710d147ebb65a076f6062d2fa3d8298e898de7f7e0d30809f`。判断ADR-0109、REQ-147、HAZ-133、FAULT-146。
固定Debian 13開発コンテナ、通常UID、3 GiB/swap0/CPU1/pids128の順次実行。

NIAGEN06を公開engineへ接続した。未受理処理はstage検査と実engine CAS予約の下で現在sourceを
照合する。実stateで同一planが受理済みの場合だけ、別型の保持stageからterminal記録を修復する。
物理stage、全journal/receipt、pin、保持閉包、現在のmanaged/供給認可は必須である。
設定の適用、filesystem切替やbootをこの証拠で認定していない。

実conffile fixtureのlocal維持/vendor退避と受理後source変更で251 assertion、
新規/activeのstage検査後変更で95/125 assertion。新プロセスのterminal再開と
6種の欠落（設定record、閉包、tar、stage/publication journal、世代pin）も成功。
受理済みstate/descriptorの無変更と欠落の非修復、独立wire/tar照合を確認した。
旧v4公開2,023、v5公開142、stage1,211、設定済み世代358 assertionが成功。
現在観測13 case、独立6 rootと既存公開oracleも成功した。

compile-01とtest-02で実compile/実行し、最終の説明comment訂正後にもcompile-03で3 mainを
強制compileした。最終binaryは実行済みbinaryとすべてbyte一致した。401 compile入力、
41 fixture、8 Python工具を正本へ照合した。構造/link/lint/license/生成CIも成功。
最初のPython oracleのpath表記とADR必須見出しの不備は失敗ログを残して修正した。

`test-02.sh`と`run-container.py`が限定実行手順である。compileは常に`gprbuild -f -P tests.gpr -j1`。
`initial-*`と`tested-pkg_generation_stage.ads`、各compile入力表に実行時source差分を保持する。
root-oracleのtar、CAS、実行binaryは私有labに置き、このGit証跡には含めない。

CIにはcheck_configured_publication.pyをcomponentと統合runnerの両方へ登録した。
GitHub上の既存niaosは別projectだったため上書きせず、push/release/remote CIは未実施。
本番provider、抽出済みrootの資格確認と実切替/boot、全DEB効果、GC、完全置換ISOと全言語翻訳は未完。

同時の利用者依頼で未使用storageを整理した。対応記録はmaintenance/storage-cleanup-20260911。
過去build cacheは削除済みで、再実行には再compileが必要。現在labと全source/evidenceは保持した。
