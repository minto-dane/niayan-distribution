# 専用bankの配備と再起動後の実device照合

source subject: `746a5a7d63171fb0666b3b9741596fc529ef7b8ebd39656ebe07c73e27311288`。ADR-0113、REQ-151、HAZ-137、FAULT-150。

0.5.0の明示bootstrapは、root所有0600のplanからGPT partition UUID・ext4 UUID・容量を受け取る。
実block FDの容量とcacheを使わないblkid probeを照合し、共有bind bankへのfallbackを除いた。
既存の排他的intentへplan hashを束縛し、mount drop-inを新規作成・同期する。
初期化時だけRWでbank provisionerを呼び、ROへ戻した現在照合後に完了記録を作る。
format、既存領域の自動移行、欠損修復は行わない。

起動前の独立oneshot guardはplan/drop-in/初期化記録、実deviceとmounted root、保護条件とbank記録を
再確認する。準備serviceはguardの成功を必須とし、従来のcapability/device viewを維持する。
unitの導入でCAS/bank作成や通常socketの有効化をしない。

VM 02では追加の使い捨て64 MiB diskにGPT/ext4 partitionを作り、導入済みpackageと実native initializerで
初期化した。formatしたのはVM fixtureであり製品bootstrapではない。
plan欠損/誤UUID/誤容量、既存core/bank/初期化記録の7拒否条件と、完了後の再初期化拒否を確認した。
実再起動後に同じbank記録のinode/hash、RO mount、guard経由のservice開始を確認した。
mount IDは再起動前69から後67へ変わり、永続planから現在値を再観測した。
plan変更によるservice開始拒否、bank lock欠損の非再生成、同じinodeを明示復元した後の照合も成功した。
これは実root/boot世代の切替や、物理電断受入ではない。

VM 01はguard unitの梱包漏れを検出した。install manifestを修正し、初期化前のloaded/inactive検査にも
guardを含めて、新規VM 02で確認した。初回ログと入力を保持する。
最終main DEB/dbgsym/source dsc/source tar.xzは別directoryの二重buildで同一bytesだった。
26 export入力をsource packageへ、30 runtime fileを正本/既存受入へ照合し、DEB内module/unit/workerも確認した。
workerはb55000d2e21d96c8e75a9f36dda4bbcf5c77c9dbf42074fa39b1600b1c113322で不変。
initializerは以前の受入packageの実binaryを使用した。appと共通vendorは当時と不変で、全componentを最新buildした
という主張ではない。構造/参照/lint/license/生成CI整合性が成功し、Ada全suite/証明や旧service fixture全体は反復していない。

外側3 GiB/swap0/CPU1/pids128、VM 2 GiB/1CPUで順次実行した。全VM jobは終了した。
使い捨てVM差分2個と追加disk2個、計99.03 MiBを削除した。base/受入VM、対応source/package、
入力archive、既存SDK/initializer buildを保持する。Git証跡にはVM/CAS/binary/秘密鍵を含めない。

UUIDは暗号学的なdevice認証ではない。clone/hotplug、privileged remount/raw-device writerの排他は
別のcontroller責務で、検査結果を永続boot許可にしない。旧bind bank/旧完了記録は自動移行しない。
LUKS/device-mapper/RAID等の別profile、完全置換ISOのpartition recipe/UI、本番controllerの認証/RPCと
全寿命排他、bank slot/GC、全DEB効果、実root/boot切替と復旧、全言語翻訳は未完である。
