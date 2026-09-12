# 旧root準備serviceの撤去・更新受入

2026-09-12。旧service/socket、専用C/Ada RPC、専用dev viewとVM bridgeを撤去した。
共通Bank、bootstrap、永続intent/result、予約、FrozenRootと保持root-sessionは維持する。
判断は[ADR-0120](../../../../assurance/docs/engineering/adr/ADR-0120.ja.md)。
この撤去フェーズの受入であり、本番認定ではない。

source subjectは`daac325557fae401f562333cb5cf1ff84c0bc5c7603736dc4d1ee5e3e4320ba8`。
`report.json`に変更前のGit参照、入力hash、実行条件と限界を記録する。

## 実行した範囲

- 世代SDKを必須transportへ統合し、独立observer、全認可、現在設定/保持内容、実FDと三予約を維持した。
  v5のrun_root_archive_testsは1,631 assertion、v6のrun_root_configuration_testsは1,206 assertionを通過。
  事前拒否、送信後拒否/例外、事後identity/元期限/認可/設定元の変更、busy handle、期限後の予約保持とCloseを含む。
- 設定entry観測141、通常世代stage 1,211 assertionも通過。UID0は1,133 assertionのmainで
  準備・再検査のobserver/transportより前に拒否した。assertion数を独立した試験数と数えない。
- root sessionのC/Ada往復は29項目成功。実peer/FD/credential/pidfd、有限期限と解放を使うが、相手と物理identityはfixtureである。
- 実VMで共通Bankの排他・誤予約・重複拒否、実worker、保存記録の再観測、intent fsync後の所有process SIGKILLを確認。
  9種類の物理root再検査とreadonly/束縛/記録不変も確認。SIGKILLはworker開始前の明示fault pointである。
- 旧0.7.0→0.8.0のオフラインchroot unpackで旧unit/devとRPC入口の不在、共通Bankと既存復旧記録の保持を確認。
  このchrootではconfigureを実行していない。新規VMへの0.8.0の完全なpackage導入/configureは別に実行した。
- live更新は旧版（storage未初期化）と後継listener稼働中の双方で拒否。コード・保存物・unit状態/PIDが不変だった。
  動作中workerへの更新試験ではなく、live更新を状態にかかわらず拒否するpolicyの検査である。
- 後継unitで明示GPT/ext4 bootstrap、誤device計画・既存state・root initializer拒否、readonly再起動を確認。
  有効な実要求でbank lock/CAS lock/policy欠損を拒否し、再作成しなかった。実prepare/freeze/observe/close、
  CAS再取得、Bank保持、元tree/記録不変、別の再起動後のROと旧受付不在も確認した。

package 0.8.0のmain DEB、debug DEB、DSC、source tar.xzは別の二つのbuild directoryでバイト一致した。
main DEB SHA-256は`ba88f35d97df513ee0c3a194944f407c312038eb225ce311a48057e32067473e`。
`artifact-check.json`は配布された選択source/unit、native入力、旧RPC symbol不在、実行用tarを現行sourceへ照合する。
初期化器は不変の既存受入binaryを照合して再使用したもので、今回の再buildとは数えない。

コンパイルimageは`sha256:76d5c00dfa833ce7ae67a192c5663d9bcd5c4104153f5933431dae88c097918c`。
QEMUを含むVM工具imageは`sha256:7f92f64938b87b862dd962a93b558fb0caea13493745c684fbddfc190a723617`。
重いjobは逐次、3 GiB/swap0/CPU1/pids128。VMは2 GiB/1 CPU、閉じたネットワークで実行した。
構造/参照/lint/license/生成CIも成功。旧C通信150行を削除し、数学的src/vendorは変更していない。
新しい形式証明や全C/FFI/runtimeの適合認定は実施していない。

## 準備失敗と修正

`attempts.json`に主要な準備失敗とcoverage訂正を記録する。3秒の試験期限は検査中にStaleとなり、
試験だけを30秒にして実期限切れまで待つ形にした。製品の期限検査と資源上限は変えていない。
VM工具image/実行UID、guestのPython検索pathを修正し、作成済みpackageと停止済みVMを再使用した。
設定entry観測だけをv6世代受入と誤認した点は、実際のv6 mainの追加実行で訂正した。
その最初の起動も媒体pathが相対だったため拒否され、絶対pathで再実行した。
成功のない途中試行を最終成功に合算しない。

`cleanup.json`に終了した今回のVM overlay/試験state/旧SDK cacheの削除を列挙する。
解放した割当量は215,363,584 byte（約205 MiB）。現在のbuild、必要なpackage/source、共有builder、
無関係のVM/アプリは維持した。KVM deviceの権限は変更していない。

## 残る本番条件

非root世代SDK→handoff→保持sessionの本番認可/正確な計画同意/独立観測/物理取消は未接続。
実boot切替・復旧、全writer/slot/保持/GC、全DEB効果、APT完全置換ISO、全言語翻訳、
残るC/Ada FFI/特権Pythonの形式検証・厳格規則適合は未完である。
媒体電断の完全な検査、管理者独自unitの移行、remote公開も行っていない。
旧sourceの過去受入をこのsourceの新しい受入とはしない。
