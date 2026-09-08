# Nia OS 製品アーキテクチャ 0.1

> 保存した独自カタログ研究モデルの文書です。Debian 13の実配布方針は[現在の設計判断](decisions/0001-debian13.ja.md)を参照してください。この文書の機能が実イメージへ接続済みであるとは扱いません。

## 規範とスコープ

単一供給元: Debian 14 Forky、amd64/all。対象OS: Nia OS。パッケージ入力形式: DEB。内部正本: パッケージ形式から独立したNia catalog/契約/管理状態。開発ソースであり、正式リリース/ISO/本番認定ではない。

現行の製品仕様はこのdocsと`distribution/profiles/nia-os.json`、`contracts/`である。既存各componentのAPI/永続形式仕様は、そのcomponentの実装を説明する。旧Fedora/SUSE/Alma/RPM配布・管理引継ぎの文章はNiaの製品要件ではない。衝突時は本製品仕様と最新ADRを参照し、コードが追従していない箇所は実装gapとして保持する。

## 七つの責任

```
      原本DEB + Sources + buildinfo + 外部証拠
                          |
             非特権 intake / proposer
                          |
       native意味と入力閉包 → 中立モデル
                          |
                resolvercore 独立検査
                          |
   assurance信頼・認可  +  configcore設定契約
                          |
               controlcore（公開CLI nia）
                   /                \
       pkgcore ファイル/catalog   statecore サービス/HA
                   \                /
             状態・ログ・独立証拠の再照合
```

役割の追加で正本を増やさない。libsolv/CaDiCaLは提案器に限る。SATの答えも内部ruleも信用せず、元の意味、選択集合、順序、資源所有権、現在の認可を再検査する。UNSAT proofは正確な閉じたuniverseの範囲に限定し、parser/変換の正しさを証明したことにしない。

`nia`は現行管理CLIのpublic alias。暗号domainやMC_*型を文字列置換で変更しない。対象profileとartifactを署名へ束縛する。古いプロファイル用に発行した証拠がNia用に使えるとはしない。

## 変更の状態

受領→入力認証→意味計画→隔離staging→回復点確保→消費者静止→変更→再生成/意味検査→サービス反映→安定観測→承認、を分ける。途中の応答喪失は未実行ではなく結果不明。再実行は同一ID/実記録との照合を経る。

APPLIED/ACCEPTED/COMMITTEDに相当する段階を持つが、各段階をOS・パッケージ・業務データの同一トランザクションと呼ばない。既存サービスは古い実行個体を使っている可能性がある。Installed/Running/Acceptedは独立した値である。

root rollback、package inverse操作、サービス再起動、DB restore、クラスタ所有権移動は別の操作。新しい信頼・失効状態や正当な業務データを、古いrootと一緒に無条件に戻さない。

## 設定・ID・MAC

configcoreは旧ベンダー既定値/管理者意図/新ベンダー既定値を区別する。DebianにSUSEの`/usr/etc`方式を一律に押し付けない。各プログラムの本当のInclude/drop-in/env/起動引数/生成物/動的APIの入力閉包と優先順位を採用する。未知を安全として補完しない。

初期製品のMACはAppArmor。正確なサービス別profileをenforceし、弱いdefaultやcomplainを合格扱いしない。旧`MC_Platform_Profile`等のSELinux専用モデルは、Nia全体のMAC資格を判断するgateとして使用しない。対応済みのNia admission adapterが必要である。型や説明の変更だけで旧gateを通すような偽装はしない。

UID/GIDとservice identityの割当はNia catalogに来歴付きで保持する。tarの数値owner、元パッケージの動的ユーザー作成、既存データの所有者が一致しなければ変更しない。秘密情報はimage、一般ログ、環境変数、native scriptへ渡さず、範囲・期限・参照先を限定する。

## ネットワーク・時刻・管理

NetworkManagerをネットワーク構成の実行者とし、Niaが計画とcheckpoint/独立到達性/確定を調整する。nftables方針、管理経路、fencing経路、replication経路を別資源として管理する。初期SSHはnode登録と認可鍵/MACが整うまで公開しない。旧設定を根拠なく全インターフェイスへ公開するfallbackはない。

時刻源は一つの運用上の責任者とする。時刻巻戻りや不確かさをfreshnessへ伝え、TTLだけで資源所有権を解放しない。time不明やmanagement停止で、無関係の正常な業務サービスを一括停止しない。書込所有権が不確かならその資源を隔離する。

## HA / RAS

参照クラスタは3独立故障領域。quorumと実データ経路のfencingを分離し、二重writerを排除する。更新予約はquorum・サービス残存数・fault domain・追加故障余力へ束縛する。systemd、Nia healer、cluster managerの再起動判断者を一つにする。

ハードウェアRAS/EDAC、storage checksum、電源・ネットワーク・時刻・watchdog、kdump/pstore、障害IDを相関する。診断記録は機密データとして保護する。誤った自動修復で証拠や正当なデータを上書きしない。

このアーキテクチャは既存のHA/RAS SDKを再利用するが、物理fencing・DB昇格・センサー取得・遠隔control HAのサイト接続が完成したことは意味しない。

## 適用・除外範囲

最初はserver/applianceの同一OS供給を資格化する。interactive/GPU roleも同じOSの上で別の機能受入を行うが、初期のamd64/all readerはi386 multiarch gaming closureを認定していない。Steam・CUDA・サスペンドの完全動作は独立試験が必要で、NiaをDebianの公式サポート対象として扱わない。

永続領域はXFS、ESPはFAT32、volatile領域はtmpfsとする。metadata健全性・内容真正性・媒体健全性を分けて扱う。

root filesystem、boot、backupの具体契約は[storage-boot.ja.md](storage-boot.ja.md)、元形式と所有権は[ownership-and-effects.ja.md](ownership-and-effects.ja.md)、出荷は[build-release.ja.md](build-release.ja.md)を参照する。

## 正しさの主張

SPARKの仕様・契約は証明義務であって、証明成功ではない。Adaコンパイル/実行/GNATproveは本配布で未実施。Linux、filesystem、crypto、FFI、compiler、解析器、観測器には明示的な信頼前提がある。

保証は対応する版・成果物・構成・hardware・故障モデルの組に対して行う。「全故障」「全ソフト」「全未来版」の宣言を受入条件にしない。今回の独立した文書/コード参照検査も、意味同値の形式証明ではない。

## アプリ配備と破損復旧

CapsuleはNiaカタログの第一級deployment。capsulecoreが型付き能力・世代・broker条件を提供し、物理実行は資格済みexecutorへ接続する。Flatpak installed stateは導入しない。アプリ可変データと配布世代を別管理にし、世代更新でデータを無断に戻さない。

core/catalog/historyの復旧は、独立した受入anchorに結び付くcohortから行う。単一の現行diskが失われても検証できるように、rescue・原本・trustを別に保管する。完全な原本が失われたhistoryをファイル一覧から作り直さない。詳細は[cohort](../../assurance/docs/engineering/specs/cohort-recovery.ja.md)と[Capsule](../../capsulecore/docs/architecture.ja.md)。
