# 確定済み世代を基準にした更新計画

`Pkg_Generation_Publisher.Read_Current_Transition`は、確定済みの正確なdescriptorを指定し、
候補catalogへの通常更新を同じpublication/root/CAS予約の下で検査する内部SDKである。
[現世代の読取](current-catalog.ja.md)、[通常更新の意味](transition-plan.ja.md)、
[世代の保持](generation-retention.ja.md)を接続する。

## 入力と検査

Expected_Currentは期待するdescriptor全192 byteのSHA-256である。catalog hashや世代番号だけに
置き換えない。現在の受理済みdescriptorと異なればStaleとする。初期世代・未確定transaction・
欠落したjournalやlockを、空の正常な前世代として扱わない。

候補はTarget_CatalogとTarget_ClosureをCAS digestで指定する。基準世代のmanifestとpin、
基準と候補の正確なcatalog保持閉包を検査してから、両catalogを元DEBから再観測する。
保持された派生objectが欠けていれば失敗し、自動再構築による成功に置き換えない。

Native_ArchitectureとEnabledは明示的な入力である。Pkg_Deb_Transition.Buildで候補の
最終依存集合・共存条件と、基準に存在するEssential/Protectedの維持を検査する。
候補の存在や保持hashの一致だけでは、依存関係の成立を認めない。
壊れた前世代からの通常修復は従来のtransition規則に従い、保護移行や初期構築の例外は追加しない。

最後にroot.stateの完全一致と有限BOOTTIME期限を再確認する。UID0、期限切れ、無期限指定、
別root、予約競合では成功結果を返さない。失敗は以前の成功を含めCurrent・Plan・Bindingを消す。
native transitionが出した失敗理由だけを言語非依存のFindingとして残す。

## 結果の束縛

成功時は受理済みdescriptor、sealed transition、Bindingを同時に返す。
Bindingは次の136 byteのSHA-256である。第二の導入済みDBや新しいpinは作らない。

| 0起点offset | bytes | 内容 |
| --- | --- | --- |
| 0 | 8 | ASCII `NIAUPD01` |
| 8 | 32 | 正確な受理済みdescriptorのSHA-256 |
| 40 | 32 | 候補catalogのSHA-256 |
| 72 | 32 | 候補保持閉包のSHA-256 |
| 104 | 32 | native transition fingerprint |

transition fingerprintは前後catalog、全変更と、architecture policyを含む最終集合検査を束縛する。
同じ内容でも別のarchitecture policyならBindingが異なる。同じ入力の再観測は同じ値を返す。
変更なしの場合も、正確な基準descriptorへ束縛する。

## 呼出し後と未完の接続

返却時に予約は解放する。結果は更新計画の観測であり、署名・供給認証・実行許可ではない。
本番admissionはpolicyの出所、現在の同じdescriptor、全phase/effect/所有権と保持を
実行時の予約下で検査する必要がある。現在のPublishは正確なpredecessorを再照合するが、
この新しいBindingを本番認可へ自動的に取り込む機能はまだない。
逆方向の計画を作れても、rollback floorの許可や実データの巻戻し可能性は別の条件である。

## 検証

既存の二世代公開・復旧試験へ、変更なし・順方向・逆方向の18観測と四つのBindingを追加する。
独立readerが元DEBと実root.stateから前後catalog、architecture policy、全変更とBindingを再計算する。
候補のclosure自身と全memberの8欠落、基準世代の保持欠落、誤ったpredecessor/closure/root、
予約競合、期限、不成立の依存集合、policy変更を検査する。
試験のauthorityとrootのtree/versionは合成であり、全DEBの物理適用・実起動の受入ではない。
