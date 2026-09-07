# 署名付き入力とKIWI組立て

## 実装済み工具

Pythonは開発/組立て工具のみ。特権の管理コアはAda/SPARK。
`distroctl.py`はネットワーク取得・RPMインストール・サービス開始・鍵作成をしない。
信頼済み別経路で用意した二者(build/security)の公開鍵から、入力envelopeのEd25519署名を検証する。
同一鍵/同一承認ドメイン、期限切れ、世代巻戻し、異なるfamily、署名後改変、ソース/契約の不一致を拒否。
CLIは人工test_only信頼情報を受け入れない。

既存バイナリを完全なローカルスナップショットへ取得することは、すべてを再ビルドすることではない。
SLESの認証情報をURL・recipe・ソース・ログへ含めない。取得は適格な別工程で行い、snapshotをread-only化する。

```text
python3 distribution/tools/distroctl.py profiles
python3 distribution/tools/distroctl.py verify-inputs \
  --profile sles-16.0 --lock /PRIVATE/release.json --trust /TRUST/authorities.json \
  --cache /READONLY/snapshot --minimum-generation 7 \
  --expected-source-set APPROVED_SHA256 --expected-contract-profile APPROVED_SHA256
```

`render-kiwi`に同じ引数と`--output /PRIVATE/config.xml`を与えると、検査成功後に新しいXMLを作る。
既存outputを上書きしない。APPROVED値はenvelopeから転記せず独立した受入計画から得る。

## チェックするもの

- 全input file集合(欠落/余分/リンク/特殊ファイルを含む)とdigest。
- repomdのdigest、metadataのhash/size、primary XMLの安全な解析、locationの範囲、NEVRA/hash一致。
- UTF-8 JSONの重複key・未知field・浮動小数などの拒否、構造の上限。
- 暗号が正しいことと、元RPMの署名・依存関係・起動可能性の資格化を分離。

RPM-MDはgzip/xz/bzip2/uncompressed primary XMLを有界に扱う。未知compressionは拒否。
DTD/entities、XML base、外部URL、親path、弱いhash、alias/重複locationを受け入れない。
primary以外も記載metadataのhashを照合するが、そのすべての意味を実装するresolverではない。

## KIWI

[KIWI](https://osinside.github.io/kiwi/quickstart.html)を使う設計であり自作installerを新設しない。
[XML要素](https://osinside.github.io/kiwi/image_description/elements.html)に従い、RPM-MDローカルrepository、
repository/package署名確認とrpm-check-signatures、UEFI、GRUB2、BLS=falseを出力する。
packageの架空version属性は使わず、承認済みsnapshotに依存する。build後に全installed NEVRAと比較する。

このXMLは起動可能性の証明ではない。KIWIの正確なschema検査、依存解決、起動・rescue・upgrade・
Secure Bootの試験は未実施。bootstrapパッケージの完全なclosureはsite build工程の責任。
metadata labelがNEVRAと一致することはRPM header/payload署名を実際に検証したことではない。
KIWI段階のGPG検査も必要であり、署名に失敗しても--no-gpg-checkを追加してはならない。

## 機密情報と同一性

clone対象imageへmachine-id、SSH host秘密鍵、TPM sealing secret、MOK秘密鍵、node証明書、
クラスタトークン、過去ノードの再送台帳を焼き込まない。node固有の認可は隔離されたcommissioningで行う。
同じ公開imageを複製しても、node/boot/clusterのidentityが共有されないことを受入試験する。
信頼世代・失効情報と業務データをOS rollbackへ巻き込まない。

## 工具の依存関係と権限

Python 3.10以降、`cryptography`（Ed25519）、`defusedxml`が必要。Python工具は形式検証対象ではない。
試験・ビルド用の隔離環境で、配布元の署名済みパッケージまたは監査済みハッシュ固定依存を使用する。
rootへのネットワークpip実行を必要条件にしない。取得環境と、入力を固定して組み立てる環境は分離する。
署名が正しくても本版の固定profileに反するSELinux/Secure Boot/所有権/購読要件や、
`production_qualified=true`は拒否する。異なる役割で同じ承認IDを再使用することも拒否する。
