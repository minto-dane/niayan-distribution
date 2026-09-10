# 保護site供給providerと実publisher接続

対象source subjectは`4e9865f5ff59e92bf042d26ce22215f15c02190ca8c3abeebef43f410e0c55fe`。pkgcore commitは
`9de3fe6542f9cf497434855de17af602f998165e`。compile対象source362個とVM入力15個は
最終source/配布入力に一致する。input-verification.json、source-inputs.json、vm-inputs.json参照。
判断はADR-0090、配備契約はdistribution/native/site-supply.ja.md。

## 実装と境界

Pkg_Site_Supplyがroot所有の現在policyと独立floorからscope/key/epoch/ageを読み、実UTCを採取する。
全祖先と通常fileの所有/mode、正確なwire、root identity、完全policy hash、serial/UTC下限、
期限を確認する。CASや保持policyの自己申告を信頼入力にせず、CASを再取得しない。
root/transaction/physical plan/retained policy/mapと初期policy/floorをsessionへ束縛する。
各観測で再検査し、変更・欠損・拒否時は全出力を消してsessionを閉じる。自動的に旧sessionを復活させない。
内部pkg_supply_observeはDEBの/usr/libexec/niaへ配置する読取専用の配備確認工具である。
共有vendor/API、元DEB、NIAGEN05/NIASPOL1と既存managed guardは変更しない。

これは供給policyの独立した観測であり、署名記録発行・同意・全効果・health・世代認可を
すべて提供するものではない。policy/floorのfile hashと所有検査はhardware rollback耐性ではない。
正しい時刻、rollbackから分離されたfloor、認可済みのpolicy配備はsite/installerの責務として残る。
既定policy・本番鍵・常時成功callbackは配布しない。

## 検証

Debian 13のGNAT 14で新しい内部appと二つのAda test mainをcompileした。
形式/境界/拒否出力248 assertion、既存世代公開の回帰2023 assertionが成功した。
最後にspecの説明を明確化した後も二つのmainを再compileし、最終sourceをVMで使用した。
標準Ada mainへの登録とCI/API inventoryは正規工具で更新し、traceability/構成/local link/licenseが成功。
初回の私有export更新漏れとテストの演算子可視性エラーはログへ保存し、修正後compileした。
CI生成前のAPI index更新漏れも正規inventory生成で解決し、検査を無効化していない。

clean pkgcore commitを正規component輸出工具でDEB sourceへ出力し、全6 appをlinkした。
DEB_BUILD_OPTIONS=parallel=1 nocheckを明示し、全suiteの繰返しと関連する実試験を分けた。
別directoryで主DEBとdbgsymが実バイト列一致した。主DEBは
`b1b850ecd20ecb411aaf98f7eb3708083855649578ccd463009d33e6a88f5d3c`、dbgsymは
`291d6126ead841962948e0766012ced4d02c38fc2bccee53811b0d86c4c4336e`。
実build依存版は.buildinfoに保存した。過去の固定SDK/形式証明をこのsourceの成功へ読み替えない。

使い捨てDebian 13 VMへ実DEBと実ELF依存libgnat-14を導入し、以前受入済みの
root準備0.2.0のsysusersで専用UID987を用意した。builder内のdpkgは検証工具である。
20 probe caseで正規policy、UID0拒否、hash/serial/時刻/root/件数/key/epoch/mode/owner/
欠損/symlink/writable祖先を確認した。観測中にpolicyのinode/mode/owner/contentは変わらなかった。

root管理者の原子的policy更新、floor変更、floor欠損の三場合では、同じ実sessionを二回観測し、
拒否と全出力消去・sessionの自動復活がないことを確認した。それぞれ253 assertionが成功した。

既存publisherのObserve_Supplyへ実providerを接続し、現在時計の人工署名receiptを使用した。
正常系は109 assertion、公開中に16回の独立観測を行い、実root/CAS予約下で処理を完了した。
現在の保護policyの鍵とepochをそれぞれ変更した二場合は各79 assertionが成功し、
最初の観測で公開を拒否して初期世代を維持した。公開を拒否するtest caseのexit0は、
拒否の検証が成功したことを示し、その世代が公開されたことではない。

ここで使った他のmanaged/barrier/health/effect認可、上流原本と秘密鍵は明示fixtureである。
本番認可を完了したとは扱わず、秘密鍵・設定を製品へ転用しない。

## 実行環境と次の工程

外側3 GiB/swap0/CPU1/pids128、VM2 GiB/1 vCPU、重いjobは逐次。VMと全jobは終了済み。
変更のない全suite、全形式証明、旧カオスcampaignは再実行していない。
私有labはnative-site-supply-01。VM disk/秘密鍵/library/DEBはGitへ入れない。
GitHub公開と本番Releaseは未実施。

次は認証済み供給記録を発行するobserver/署名providerの実配備と、全managed/世代認可adapterである。
installerのpolicy/floor配備と時計確立、全DEB効果、容量/物理再検証/GC、実boot切替/復旧、
APT完全置換ISO、全言語翻訳も引き続き未完である。
