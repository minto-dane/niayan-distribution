# 元conffilesと設定更新判断の受入

subject: `809073d3409ae92de9c31b3e5b03260065c32d572e00be97a8c82b8324576926`。
判断ADR-0095、仕様distribution/native/conffiles.ja.md。

元DEBから設定宣言を読み、元controlと対応payloadへ束縛するnative層を追加した。
内容判断は旧vendor/local/新vendor、削除状態、確認要求と退避を区別する。
通常削除・purge・remove-on-upgradeと現行baselineを扱う。全属性とリンク種別は保持し、
判断だけでhost書込・リンク追跡・全managed認可を行わない。

## 実行結果

- GNAT14/Cで実compile/linkし、18原本fixtureを含む99 assertionが成功した。
  宣言の不在/空/欠落payload、flag、末尾改行なし、空白名、非UTF-8 byte名、symlink保持と
  blank/重複/未知flag/unsafe path/NUL/矛盾を扱い、不正inventoryを全消去した。
- dpkg 1.22.22を非root・scriptなしの私有root/DBで実行した。最終upstream-04の126 caseで
  設定内容、確認要求、退避内容、次回vendor baselineの不一致は0だった。
  新規/更新、local欠落・無変更・編集・新vendorと同一・空file、vendor変更/不変/省略/削除flag、
  未解決/keep/useの選択、通常削除とpurgeを比較した。
- 上流はMD5 baseline、nativeはCAS SHA-256で、比較時だけ同じ既知bytesから両方を計算した。
  MD5を供給署名や実行認可に使用していない。rootはすべてlab配下で、maintainer scriptは作成・実行しない。
- 共通MC_TextがASCII専用であることを検出し、設定pathをnative bounded byte stringへ変更した。
  同じ型を使っていた供給plannerのpathも修正した。共有API/vendorの書換えはない。
  plannerのUTF-8 byte保持を含む26 assertionが成功した。
- 更新driverの実配布observer VM17 caseが成功し、test/QEMU exitとも0だった。
  計画の正常二要求は各52 assertion、途中trust変更と欠損は各46 assertion。
  直接observerの正常二要求は各50 assertion、HTTPS中の競合排除は合計32回だった。
  VMはASCII fixture pathでの接続回帰であり、全Unicode名のHTTPS受入を主張しない。
- source inventory/traceability、syntax/local link、license表記が成功した。
  unified-auditの範囲はpass-source-structure-only。数学的入力は不変で形式証明は再実行していない。

369 compile入力、19 fixture file、65 VM sourceと全79 VM入力を照合した。
conffile driverは`16b9852f15069ea5f141232f8b82056024a0ca3fc1aa8916aaaef20006ec7e94`、
observer driverは`d88def2d4cae58ab414a1a7e243f90b2379bed5204c1142c03ac6e797871bbe2`。
serviceの22配布入力は不変で、既存DEB
`3d393d248edf558e4b6344e2dddc8db280d4cdd308a05a519396ea128bd32c6b`を再利用した。
新reader/判断を六appや稼働rootへ配布したという意味ではない。

## 修正と証拠の範囲

初回test構文とPATH不備、ASCII制約を修正し、失敗ログを保持した。
upstream-01/02は内容・確認・退避の比較が成功したが、全metadata比較ではなかった。
追加調査でremove flagでも旧vendor履歴が残ることを確認して修正した。
upstream-03のmetadata比較では、宣言とlocalがともに消えた三場合の追跡解除に不一致を検出した。
最終upstream-04で修正し、全126 caseの詳細ログと判断を保存した。初期reportも残す。
同じ全suiteや旧カオスの反復は行わず、変更した意味とpath接続を検証した。

全local inode/属性の予約下観測、利用者選択と退避名衝突の認可、履歴保持、生成script、
リンク/所有権、全root組立てへの設定反映、全managed認可と公開controllerは未完。
本番site鍵/floor/時計/installer、全DEB効果、容量/GC、実boot/復旧、完全置換ISO、全翻訳も未完。
VMのCA/TUF/key/DEB/root contextは人工fixtureである。内容判断を実適用や独立認可へ読み替えない。

外側3 GiB/swap0/CPU1/pids128、VM2 GiB/1vCPUで逐次実行した。全VM/jobは停止済み。
秘密鍵、VM disk、実ELF、比較用DB、配布DEBをGitへ含めない。私有labはnative-conffiles-01。
