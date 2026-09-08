# XFS健全性・修復契約

> 保存した独自カタログ研究モデルの文書です。Debian 13の実配布方針は[現在の設計判断](decisions/0001-debian13.ja.md)を参照してください。この文書の機能が実イメージへ接続済みであるとは扱いません。

## 対象と保証範囲

Niaのディスク永続領域はXFSを用いる。正常性は次の三軸に分ける。

1. メタデータの構造・相互参照の整合性。
2. 媒体の読み取り・書き込み、冗長経路、電源断時の永続化。
3. ファイル内容・属性・設定・業務データの意味と真正性。

XFS online scrubとrepairは主に1を扱う。media verificationとI/O error通知は2の証拠になる。3は認証済みNiaカタログ、改変検査、必要なアプリケーション検証、独立バックアップによって扱う。metadataのHEALTHYイベント、scrub成功、暗号化、RAIDだけで3を承認しない。読み込みごとの暗号学的内容検証をこの構成が実装済みとは表示しない。

## 供給・実行能力

Linuxとxfsprogsは別の成果物である。カーネル7.0以上、xfsprogs 7.0以上を入口条件とするが、それだけでは十分でない。CONFIG_XFS_FS、CONFIG_XFS_ONLINE_SCRUB、CONFIG_XFS_ONLINE_REPAIR、実際のioctl、イベント配送、必要な逆参照メタデータ、rescueの互換性を、正確なビルドと対象マウントで検証する。

`xfs_healer`は上流で実験的とされている。自動修復にはそのリスクの独立レビュー、退避先、復旧試験、上限、停止方針が必要である。パッケージ配布状況は[供給観測](../contracts/xfs-supply-observation.json)へ記録し、URL上の最新版をそのまま受入済みバイナリにしない。

## 三つの実行責任

**定期検査**: `xfs_scrub -n`による全域のmetadata検査を行う。対象UUID、実マウント、起動個体、開始終了時刻、対象範囲、終了コード、診断記録を保存する。終了コード2は最適化提案であり、内容認証でも運用上の全正常でもない。timeout、信号終了、部分走査、Operational/Usageエラーを正常に変換しない。

**イベント監視**: FSごとに一つのnative health monitorを所有する。診断プログラムが別のmonitorを奪わない。`xfs_healer --no-autofsck`を用い、FSプロパティのautofsck=repairによる暗黙の修復を監視モードへ持ち込まない。nativeの`xfs_healer_start`とNiaの管理が同じFSで並行しないよう、受入時に所有者を検査する。

**修復**: Niaの計画・認可・永続予算・独立証拠の保存後、資格化されたnative修復器だけに委任する。既定のサービス定義は監視と非修復scrubのみで、自動有効化しない。自動修復セッションを開く接続はサイトで認証・資格化する。強制ログ破棄、検査を避けたmount、侵害証拠を消す修復、同時の別repair writerを許可しない。

`xfs_healer --repair`は対象修復失敗やlost eventで全scrubのサービスを起動し得る。資格化する場合は、その補助サービスまで同じ認可・記録・予算・停止条件へ拘束する。主プロセスだけ停止して全副作用が終わったと見なさない。開始済みkernel ioctlは通常の制御フラグでは取り消せない。

## イベントと完全性

各イベントはnode、boot、filesystem UUID、mount ID、mount namespace、cohort、policy、stream epoch、単調なsequenceへ拘束する。kernelイベントのUnix時刻を、そのままNiaのboot内単調時刻と比較しない。登録済みcollectorが元の記録を保存し、受信時刻・時計の不確かさと変換規約を証拠へ含める。

HEALTHYは個別metadata項目に関するイベントであり、全FSの正常宣言ではない。LOST、sequence欠落、observer再起動、unknown eventを検出したらcoverageを無効化する。再開したstreamと完全な非修復scrub、内容・媒体の再検査が必要である。無イベントは潜在破損の不在を示さない。

filesystem shutdown/unmount、媒体エラー、file I/O error、content mismatchは別々のラッチにする。正常metadataの通知だけでは解除しない。修復結果不明の場合は同じ操作を再送せず、保存済みrequest IDを照合する。試行予算は再起動や正常通知でリセットしない。Rebindは旧実行個体の停止と認証済みreceipt、新しいstream epochを要求して予算・媒体/内容faultを保持する。pending repairがあれば再束縛を拒否する。起動が変わった場合だけ新しい単調時計の原点を認証付きで受け入れ、以前のscrub・内容検査時刻は破棄する。同じ起動での時計巻戻りは拒否する。

## 再受入れ

オンライン修復完了は、全体復旧完了ではない。全域scrubと内容検査には別の期限を持たせ、古い内容検査を継続承認へ流用しない。修復後に開始された全域scrub、Niaカタログの内容・属性、設定と生成物、業務ヘルスを検査する。途中の新しい異常、未収集イベント、対象の差し替え、trust floorの更新は以前の証拠を失効させる。検査済みという自己申告を署名の代用にしない。

metadataを再構築できない、媒体に障害がある、正常な原本を特定できない場合は、対象資源の隔離・処理退避・停止したFSの回復へ進める。全体バックアップからの復元でも、制御ログ、失効情報、正当な業務データを過去のOSに合わせて削除しない。

## 実装境界

- `State_XFS_Health`: SPARKの判断・状態遷移。記録の検査、損失ラッチ、repair予約・結果不明、再検査を扱う。Ada実行・形式証明は未完。
- `State_Storage_Integrity.Evaluate_XFS`: XFS用判定から既存のstorage health判定への接続。返り値は全システムの書込許可ではない。
- `nia_xfs.py`: 閉じた製品契約、診断用の事実検査、実mountの限定的な読取。署名発行・ioctl操作・修復はしない。
- `nia-xfs-observe@.service`と`nia-xfs-scrub@.service`: native工具に渡す非修復定義。実機起動・性能・完全なイベント収集は未試験。

SPARK状態の全遷移は既存の永続管理器へ保存してから実効果を出す必要がある。callerのauthenticated等は信頼境界であり、未認証のJSONからそのまま設定しない。新規Initializeはbootstrap/再commissioning用であり、既存の予算やpending操作を消す手段にはしない。全workerへの強制接続、署名collector、永続repair executorは未完成の接続である。

## 診断

```
python3 distribution/tools/nia-distroctl.py storage-policy distribution/contracts/xfs-policy.json
python3 distribution/tools/nia-distroctl.py storage-inspect /
python3 distribution/tools/nia-distroctl.py storage-assess POLICY OBSERVATION EXPECTED NOW_MS
```

すべて`execution_permit=false`。inspectはmountinfoと実際に開いたdirectory FDを照合する。geometry、ioctl、data integrityは未観測として出力し、稼働するhealth monitorを開き直さない。

## 一次資料

- https://man7.org/linux/man-pages/man8/xfs_healer.8.html
- https://man7.org/linux/man-pages/man8/xfs_healer_start.8.html
- https://man7.org/linux/man-pages/man8/xfs_scrub.8.html
- https://man7.org/linux/man-pages/man2/ioctl_xfs_health_monitor.2.html
- https://docs.kernel.org/filesystems/xfs/xfs-online-fsck-design.html
- https://docs.kernel.org/filesystems/fsverity.html
