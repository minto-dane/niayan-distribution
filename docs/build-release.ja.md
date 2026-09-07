# Nia OS の組立て・配布・初回導入

## 供給と製品を分ける

公開Debian mirror/snapshotから取得した原本DEB、Sources、.buildinfoと、Niaが生成するcatalog・設定・UKI・rootイメージは異なる成果物である。元DEBの署名・再現性を派生イメージの資格へ自動転記しない。

ビルド室の既存管理器はtoolsとして使えても、ターゲットrootのpackage writerにはしない。Niaの6 componentをビルドし、各`packaging/nia/artifact.json`へ実行ファイルの出力が一致するか検査する。旧RPM specは歴史的なビルド補助で、Niaの配布プロファイルでは使わない。

## 取り込みCLI（非特権・オフライン）

```
python3 distribution/tools/nia-distroctl.py profile distribution/profiles/nia-os.json
python3 distribution/tools/nia-distroctl.py layout distribution/contracts/state-domains.json
python3 distribution/tools/nia-distroctl.py inspect-deb /absolute/input.deb
python3 distribution/tools/nia-distroctl.py verify-deb SNAPSHOT KEYRING TRUST_JSON main/binary-amd64/Packages.xz pool/main/.../artifact.deb
python3 distribution/tools/nia-distroctl.py verify-source SNAPSHOT KEYRING TRUST_JSON main/binary-amd64/Packages.xz pool/main/.../artifact.deb main/source/Sources.xz
python3 distribution/tools/nia-distroctl.py buildinfo SUBJECT_JSON BUILDINFO
python3 distribution/tools/nia-distroctl.py reproduction RECEIPT_REQUEST_JSON
python3 distribution/tools/nia-distroctl.py compose SNAPSHOT KEYRING TRUST_JSON COMPOSITION_REQUEST_JSON
```

`verify-deb`は固定されたarchive keyring/primary fingerprintでInReleaseを検査し、Codename/Origin/Label/Date/Valid-UntilとSHA-256鎖を確認する。`verify-source`は同じInReleaseが認証するSources inventoryと全source blobを照合する。自動ネットワーク取得やkeyserver問い合わせを行わない。

`compose`は独立した入力のInRelease digestに固定し、同じスナップショットのmainの成果物から、重複所有権と最終依存を確認した**候補catalog**を出す。曖昧な通常ファイルの共有所有権は、同じ内容でも拒否する。共通directoryはmode/UID/GID/xattrs一致を必要とする。

依存探索用の全リポジトリが閉じていること、全effectが安全であること、段階的schedule、liveホストへのインストールは別工程。CLIは常に`execution_permit=false`。信頼設定を入力データ自身から読み取って正当化してはいけない。trusted timeは本番では適格な時計と独立した下限から供給する。

## 再現性・出所

Sourceの`Version`とbinNMU後のbinary Versionを文字列操作で同一視しない。原本DEBのハッシュを.buildinfoのChecksums-Sha256へ直接照合する。buildinfoが一致しても再現ビルドを実施したことにはならない。

二者のreproduction receiptは、正確なDEB/source manifest/buildinfo、Release、policy、期限を署名対象にする。公開鍵レジストリにある主体・ドメイン・失効を使い、署名者が自称した独立性を採用しない。レジストリ運用と実際の独立性の監査は別の責任である。

公開rebuild dashboardは有用な根拠だが、Nia形式の証拠を実際に供給するサービスが既にあるとはしていない。証拠欠落を自動承認や「再現済み」の自己署名へ置き換えない。

## 完成イメージの生成工程

1. 対象集合・source/ABI/設定/効果契約・生成物・実行時制約を閉じる。
2. 独立したソルバー検査を行い、レビュー済みeffectsだけで隔離rootを構成する。
3. Nia catalogとroot世代を同時に構成し、元DEBとNia派生物の来歴を保存する。
4. machine-id、ホスト鍵、enrollment token、秘密鍵、要求台帳を共通rootへ焼き込まない。
5. kernel/モジュール/initramfs/設定とroot世代を束縛したUKIと独立rescueを生成する。
6. 再現ビルド・二者受入・boot署名・配布署名を別の責任として扱う。
7. 初回導入で正確なデバイスを照合し、暗号鍵と信頼をprovisionし、通常/rescue起動とデータ復旧を試験する。
8. node固有ID/鍵/監査/観測/fencing経路を登録し、クラスタへの書込権は最後に別認可で取得する。

このZIPは1の一部と取り込み・検査・管理SDKを実装している。root assembler、イメージ書込、署名鍵運用、初回installer、実boot受入がすべて実装済みとはしない。危険な汎用shellや`dd`で穴を埋めた実行経路は用意しない。

## 出荷条件と長期運用

`contracts/release-gates.json`と`contracts/implementation-map.json`を使用する。ツールテストのPASS、仕様存在、署名された自己申告だけではproduction_qualifiedにしない。

WAL/CASのGCは、受入世代・未解決operation・逆操作・バックアップ・独立trust floor・legal holdの全参照閉包に対して行う必要がある。現行SDKの容量上限を超えたら記録を勝手に削除せず変更を止める。長期実行器の実装と試験は残る。

入手不能になった旧DEB・source・kernel module・schemaを、いざrollback時に外部リポジトリから取得できる前提にしない。認可された回復候補と復旧用鍵を別障害領域へ保持し、定期的に実復元する。

## 供給元の保守責任
Forkyがtestingの間は、内容固定だけで本番適格にはしない。通常の製品出荷にはDebian14 stableの保守条件を満たすか、Niaとして別途審査した修正供給・期限・緊急build能力・運用責任が必要。後者は未実装の現実の保守組織/サービスであり、署名やprofile flagを追加するだけでは満たさない。未修正で期限超過なら新しいnodeの受付や危険な変更を止め、事業の継続/隔離をsite policyで判断する。無関係の正常サービスを全停止する自動処理にはしない。
