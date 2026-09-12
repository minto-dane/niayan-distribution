# 保持root sessionの配備と旧受付の廃止

内部package `niaos-root-preparation` 0.8.0はroot-session controller、worker、共有Bank、
bootstrap、device guard、停止時のRO再封鎖、polkit policyを配布する。
旧`niaos-root-preparation.service`/`.socket`と専用dev view、C/Ada RPCは配布しない。
package名と`/etc/niaos/root-preparation.json`は共通storageの識別子として維持する。

## 導入と更新

`native/prepare_service_package.py`で新しい出力先へ必要な原本だけをexportし、固定builderで
`dpkg-buildpackage -us -uc`をJOBS=1相当で実行する。上流ソースを改変しない。
package導入はcore/CAS/bankの初期化もサービスの自動起動も行わない。
root-session socketはroot:root 0600で、監督側の本人確認を要求する。
初期storage作成には別途明示したGPT/ext4計画とnative initializerが必要である。

既存controllerの更新はオフライン対象でのみ許可する。稼働systemd環境でのupgrade/再導入や
既存storageへの導入はpreinstで拒否し、unitを停止したりlock/intentを消したりしない。
サービスが一時的にinactiveでもlive upgradeを許可しない。
対象OSを停止し、稼働OSの/runを共有しない復旧/イメージ構築環境で更新する。
これは制御面の更新条件であり、稼働NiaOSの別package authorityを追加するものではない。

0.7.0からの更新ではpackage所有の旧unit/dev viewを通常のファイル置換で削除する。
管理者独自のunit/drop-inは自動削除しない。復旧環境で必要な設定を点検する。
永続intent/result、bank.lock、CAS、root-session barrierを消したり自動移行したりしない。
旧バージョンのソース・ライセンス・hash付き証跡は履歴として保持する。

## 検査

配布物の旧入口不在、実package更新の削除、live upgrade拒否、unit検証、独立ビルドの一致を確認する。
`worker/check_bank_device.py`はbootstrap・再起動後の保存・専用device・変更plan拒否を扱う。
重複する旧配備試験は統合して削除した。欠損stateの要求拒否と実peer/FDは後継session試験へ移す。
`check_root_session.py`は実worker/peer/FD/切断/期限/停止時再封鎖を扱う。
実施結果はsource別の証跡を参照し、旧serviceの過去PASSを現行受入と数えない。

root sessionの存在は本番admission、正確な同意、全writer排他、boot切替の完成を意味しない。
根拠と残る条件は[ADR-0120](../../assurance/docs/engineering/adr/ADR-0120.ja.md)を参照する。
