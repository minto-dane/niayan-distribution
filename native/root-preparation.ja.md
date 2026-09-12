# 保持したnative世代からroot sessionへの接続境界

`Pkg_Generation_Stage.Prepare_Root`はNIAGEN05/06の検証済み世代を必須transportへ渡す。
`Reinspect_Root_And_Hold`はtransportに加えて独立した`Observe_Root`を必須とする。
SDKに既定socketや代替wrapperはない。旧root-preparation service/RPCは廃止した。
判断は[ADR-0120](../../assurance/docs/engineering/adr/ADR-0120.ja.md)、
配備は[service-deployment.ja.md](service-deployment.ja.md)を参照。

## 認可と予約

非特権callerと有限期限を確認し、世代/rootを予約してCASを再取得する。
全保持内容、現在の設定元、現在認可を検査し、同じ予約から実archive FDを渡す。
戻り後にもmanifest、pin、保持内容、設定元、認可を確認する。
transport呼出し以降の失敗はIndeterminateであり、盲目的な再送やfallbackはしない。
単独のtar hashやサービス応答は公開許可にならない。

再検査のobserverは元の展開期限とmount/device/inodeを独立に認証する。
期待値をtransportの応答から作らない。controllerはbank予約・書込停止・mount排他を
SDK handleのClose後まで維持し、その資源の所有者として解放する。
SDKは自身の世代/root/CAS予約とarchive FDを成功時のlimited型に保持する。
応答後のidentity/元期限変更や認可拒否はhandleを返さず、自身のFDと予約を解放する。

`Held`と`Root_Observation`は期限切れで無効になるが、排他は明示的`Close`まで残る。
開いたhandleへの再要求はConflictである。起動許可を表す型ではなく、後続操作の前には
controllerが取消・現在mount・物理排他を再確認する必要がある。

## 検証境界

`pkgcore/tests/root_archive_stage_test.adb`はv5/v6で認可/観測拒否、完全なscope、実FD、
三予約、送信後の拒否/例外、事後のidentity/期限/認可/設定元変更、期限後の無効化と明示解放を扱う。
物理identityと供給鍵/認可は人工fixtureであり、稼働製品へ配備しない。

Bank/workerの物理展開とRO検査は`worker/check_root_bank.py`、`check_root_reinspection.py`、
`check_root_freeze.py`、後継sessionの実peer/FDと停止は`check_root_session.py`で扱う。
SDK→handoff→root sessionの本番認可/供給/正確な同意/独立観測/物理取消は未接続である。
旧RPCを使用したhash付き過去証跡はその旧sourceの結果であり、新経路の受入に流用しない。

全writerの停止/回収、実root/boot切替と復旧、全DEB効果、完全置換ISOは未完である。
