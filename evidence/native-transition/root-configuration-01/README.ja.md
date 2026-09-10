# 設定選択と元rootの配置接続

対象subject: `f28773a5a30a4129de0bd7746e6aff68397ef40f3e8bb18e3d45af604a0ce17e`。本番認定ではない。

Pkg_Root_Configurationは、既存NIAROOT1の元原本と所有権検査にlive設定選択を接続し、
全path順の最終配置を作る。保持/更新/退避は完全な属性効果参照、削除はentry除外として扱う。
root/transaction/contextとincoming原本、incoming全宣言の選択網羅を確認する。
元rootのbinding、各設定entryの選択/閉包と、fileを残さないものも含む全選択参照を返す。

固定Debian 13 image、通常UID 1000、networkなし、3 GiB/swap0/CPU1/pids128で対象2 mainを
`gprbuild -f -j1`により強制compileした。最終test-05.logで配置136 assertion、既存選択270 assertion成功。
24個の元DEB fixtureを生成工具と照合した。compile-inputs.jsonの383候補入力とfixture 25入力は
作業repoとcontainerコピーが一致する。全候補入力を個別に実行したという意味ではない。

実DEBからcatalog/保持閉包/root tarを作り、実private rootとCASの設定選択を投影した。
保持/更新/削除/復元、全属性の採用元、選択参照、全宣言の網羅、別scope/原本、重複選択、
退避先と元payloadの衝突、親欠落/非directory、変更対象へのhardlink依存、途中のmode変更と期限を検査した。
配置失敗時はentryと入力bindingを消す。元tarの全展開を設定済みrootとはみなしていない。

test-01〜03は新コードの識別子/型/参照寿命/ジェネリック指定のcompile失敗で、runtime成功ではない。
修正後のtest-04は133/270 assertion成功。全選択参照の読出しを追加した最終版はtest-05を参照する。
途中ログは改変せず保持し、過去の成功を最終sourceの成功へ置き換えない。実コマンドはcommands.json。

構造/台帳/link/lint/licenseと生成CIも成功。数学的入力/共有vendorは不変。
全suite/証明/旧カオス/VMは反復していない。設定済みtarと全属性の実適用、inode効果、全過去設定の列挙、
特権observer、全managed認可、世代保持/復旧・実root/boot、完全置換ISOと全翻訳等は未完。
配置は準備時のsnapshotであり、実行直前の再確認・認可・保持を代替しない。
