# 非公開世代の組立て

`pkgcore/runtime/pkg_generation_manifest.*`と`pkg_generation_stage.*`が
非特権の隔離rootへ既存ファイルプランを段階適用する内部SDKを提供する。
公開コマンド、稼働管理器、DEB変換器、OS世代の公開器ではない。
[設計判断](../../assurance/docs/engineering/adr/ADR-0055.ja.md)を参照。

## データと呼出し

1. 独立検査したcatalog、全payload/xattrs、全分割プラン、認証対象receiptを既存CASへ置く。
2. `Pkg_Generation_Manifest.Encode`でマニフェストを作り、そのhashへ現在の認可を束縛する。
3. 必須Authorizer付きでStageを生成し、空のprivate root/stateを`Provision`する。
   四入口へ有限のBOOTTIME期限を明示する。native世代では[版付き保持](generation-retention.ja.md)を束縛する。
4. `Advance`を呼び、最大1つの非公開分割を適用・確定する。各呼出しで全マニフェストを
   再検査する。`Completed_Batches`は非公開組立ての進捗で、物理検査や製品受入ではない。
5. 全分割終了後に`Inspect`で全物理内容、項目数、全journalとpinを検査する。
   公開へ続ける場合は`Verify_And_Hold`で全体検査後も二つのstage予約を保持し、
   公開完了時に`Close`する。[公開SDK](generation-publication.ja.md)がこの接続を行う。

全関数はUID 0を拒否する。呼出し側は非公開性と管理予約を維持する。
戻り値が結果不明なら永続状態を保持する。新規rootとして再初期化したり、同じ効果を
無条件で再実行したりしない。欠落・破損・古いepoch/fenceの扱いは認可と復旧規則に従う。

## バイナリ形式

整数は既存`MC_Codec`と同じbig-endian。余分な末尾や予約byteの非zeroを拒否する。

| 0起点offset | bytes | 内容 |
| --- | --- | --- |
| 0 | 8 | `NIAGEN01`（構造形式）または`NIAGEN02`（native） |
| 8 | 16 | stage identity |
| 24 | 16 | 要求identity |
| 40 | 8 | epoch |
| 48 | 8 | fence |
| 56 | 32 | catalog SHA-256 |
| 88 | 32 | effect contract SHA-256 |
| 120 | 4 | 全項目数 |
| 124 | 4 | 分割数 |
| 128 | 32 | v1: zero予約領域、v2: 非zeroのcatalog保持閉包SHA-256 |
| 160以降 | 64×分割数 | plan SHA-256とreceipt SHA-256 |

最大512分割、1分割1,024項目、合計524,288項目。
各分割のtransaction identityはSHA-256(各形式の8 byte tag + 要求identity + 1起点分割番号u32)の
先頭16 bytes。分割iのbase/targetはi−1/iで、catalog/契約/epoch/fenceは全分割共通。
receipt bytesのhash照合だけでは認証ではなく、必須Authorizerが意味と現在の許可を確認する。

全パスは成分単位の先行順（`/`を他の文字より先に比較）で、重複を許さない。
最初の2項目は`catalog`（mode0400の通常ファイル）と`tree`（directory）。
以後は`tree/`以下で、各親directoryを子より先に明記する。親階層は64まで。
secret/trust/audit等の既存除外は論理パスにも適用する。物理形状を表せない元DEBを
この形式へ無理に変換してはならない。

## 残る製品接続

catalogの意味、緊急修正のholds、全DEB副作用、全特権属性、生成物と構成移行、
管理認可と独立trust floor、容量予約、実電源断、
実mount/boot/health/recoveryとの接続は未完。root/catalogの論理的な単一確定は
[公開SDK](generation-publication.ja.md)へ追加したが、稼働OSへの接続ではない。このSDKの分割commitを稼働rootへ転用しない。
元ISOの受入を新しい完全置換の受入に流用しない。

## 開発検証

非特権の`make compile-all build test`に登録した実行試験で検査する。
root拒否の4入口と公開SDKの3入口は、同じビルドを使う使い捨てコンテナ内で
`sh ci/generation-root-refusal-test.sh`を実行する。workspaceとpkgcoreのCIにも登録した。
GitHub上の実行は公開先で別途確認する。
