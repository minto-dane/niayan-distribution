# Fedora前提からSUSE16へ移す手順と禁止事項

これは破壊的なクロスディストリビューション変換コマンドではない。
既存Fedora hostをrepo差替えでSLES化しない。新しい隔離VM/別ディスクへSUSE16を設置して移行を検査する。

1. family/profileを選び、SLES entitlementと再配布/サポート境界を記録する。
2. x86-64-v2と対象CPU/kernel/module/LSM/HA ABIを実機検査する。
3. 正しいnative package ownerはzypper/RPMのまま、Missionの別rootと管理台帳を配置する。
4. /etc旧完全コピーと/usr/etc新既定値、drop-ins、.rpmnew/.rpmsave、include、initramfsをadapter inventoryへ登録。
5. policy/contractが変更されたため、旧証明・署名入力を自動再利用せず新profileで再承認する。
6. GRUB2/BLS=falseと署名チェーンを試験する。過去のsystemd-boot例を適用しない。
7. NetworkManager、SELinux enforcing、Pacemaker3/Corosync3/個別fence agentに実adapterを資格化する。
8. Native DB/業務構成/バックアップ/復元とnode identityを試験し、一部ノードから段階配布する。

Agamaを用いるinstaller工程はJSON/Jsonnet等の正確な16.0 schemaに照らして生成/検査する必要がある。
本版はその完全な無人installer profileや起動ISOを完成したと主張しない。
元のSLE15 AutoYaSTやRMTホスト配置を無検証で転用しない。

RPM specsのSUSE向けgcc-ada条件を追加したが、全16.0 repoにGNAT/GPRbuild/GNATproveが揃っている証拠ではない。
別の署名済み・hash固定ツールチェーンを用意し、由来・runtime ABI・バージョンを記録してからビルドする。
未審査の外部home:OBSリポジトリやランダムなbinaryをrootで導入しない。
