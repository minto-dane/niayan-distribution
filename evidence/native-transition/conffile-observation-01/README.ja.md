# 設定属性読戻しの受入

対象source subject: `0ba58e153141ae24583f7c8b2f7e2105fc07a82349c65134f2c4f3dc94c8e64b`。

最終受入は`test-04.log`。固定Debian 13環境で対象2 mainを強制compileし、
属性読戻し69 assertionと既存内容選択154 assertionが成功した。
実private root/CASから、raw filename、負/小数時刻、所有者/mode、実POSIX ACL、
空/バイナリxattrとnamespaceを読戻した。破損fieldのCorrupt、期限のStale、
桁落ち/順序違反/内容サイズ/欠損の拒否と、全状態消去を確認した。
full-widthの追加fixtureはdecode能力の検査であり、実kernelがその属性を発行/復元する証明ではない。

380 compile入力と22 fixture入力を実workspaceと照合した。初回拡張testのByte演算可視性不足も
`test-02.log`に保持し、修正後の最終sourceでcompileした。再現性固定時刻のcacheを使うため-fを維持した。
保持済み上流dpkg 1.22.22のsource/member hashと所有者/permission処理の読取範囲は
`upstream-source.json`に記録した。上流の改変やコードの取込み、署名の再検証はしていない。

source構造/link/lint/licenseと生成CIも成功。数学的入力/共有vendorは不変で、
全suite/証明/旧カオス/VMは反復していない。上限3 GiB/swap0/CPU1/pids128、全job終了済み。
秘密鍵、実設定、CAS、ELF、core dumpやVM diskはこの証跡に含めない。

全属性の採用方針、特権属性observer、全namespace/root archiveへの反映、認証UIと全managed認可、
世代保持/復旧と実root/boot公開、残る全DEB効果・完全置換ISO・全言語翻訳は未完。
