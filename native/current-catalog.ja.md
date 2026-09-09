# 受理済み世代のnative catalog観測

`Pkg_Generation_Publisher.Read_Current_Catalog`は、受理済み世代の記録と、その世代が参照する
元DEBのcatalogを同じ排他区間で検査する。計画に使える一貫した観測であり、実行許可ではない。

## 検査経路

publication.lock、root.lock、既存CASの順で予約を取る。
root markerとroot.state、accepted plan、前後descriptor、stage manifestのpin、
commit済みjournalを検査する。未確定transaction、欠落/不正な記録、初期世代は成功扱いにしない。
この記録検査は従来のRead_Currentと共通である。

同じ予約を保持したまま`Pkg_Catalog_Store.Load`を呼び、descriptorが指定したcatalogから
全元DEBのcontrolとpayloadを再観測する。最後にroot.stateが変わっていないことと期限を確認する。
全体成功時だけdescriptor、catalog、payload indexを返す。いずれかが失敗した場合は、
以前の成功結果も含め三つの出力を消す。元DEBのないcacheを成功の代わりに使わない。

`Read_Current`は従来どおり世代記録だけを返す。
元DEBやnative catalogが欠落していても、記録自体が正しければ記録の読取は成功し得る。
その結果をnativeデータの検査済みという意味に解釈しない。

## 観測後の扱い

返却時に全予約を解放する。呼出元は観測したdescriptorとcatalogを計画の前世代へ結び付け、
適用時にはその正確なpredecessorを再照合しなければならない。
既存Publishは現在のaccepted descriptorと計画のBeforeを比べ、Engineの予約取得後にも世代を再確認する。
旧観測を持っていることや同じcatalog hashだけで、更新を許可しない。

UID0は拒否する。期限は観測の前後とnative readerで検査し、同期CAS hash等には外側timeoutも必要。
CASにderived objectを補う場合があるが、root.stateやjournalの書換え、物理rootの修復は行わない。
CAS pin閉包と本番の認証済み予約、実行phase・全効果・所有権・実root/bootの接続は未完である。

## 試験

公開処理の既存復旧行列をnative catalogで実行し、全成功/失敗点で記録読取とnative観測を比較する。
原本とcatalogの欠落、root/CAS競合、期限切れ、別root、旧planの再適用も検査する。
独立したreaderが実際のroot.stateからaccepted planとdescriptorの連鎖をたどり、
二世代のcatalogを元DEBから再計算し、観測結果と保存byte列を照合する。
試験中のtree/versionは合成したstaging効果であり、DEBのファイル内容を適用したrootではない。
テスト用authorityの成功を本番の供給認証、phase/効果の認可や起動受入として数えない。
