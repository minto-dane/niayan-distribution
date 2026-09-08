# 旧ISOからNia-only置換対象を調べる

対象ISOのSHA-256は`d4c18dc0e2be653bf11a04db40db95ca0353322010133e068dda274bd4aa314b`。
固定ツールimageは`7f92f64938b87b862dd962a93b558fb0caea13493745c684fbddfc190a723617`。

`inventory.json`は完成ISOのstatus/controlから生成した観測。
2,239パッケージ、8,959 controlファイル、directoryを含む199,261種類の`.list`パスを記録する。
1,493パッケージに計2,263個の保持された効果ファイルがある。
元の最終集合のDepends/Pre-Depends未充足は0、既知の管理器関連11個を仮除外した場合は12。
自動削除や依存宣言の改変は実行していない。

実行工具を`tools/`、資源上限を`run.log`、コピー後のhash照合を`input-verification.json`に保存する。
`.list`の個数は変更数でも実ファイル属性の観測でもない。最大のパッケージは
`kf6-breeze-icon-theme`の39,908エントリーで、現在のファイル変更planの1,024件上限へ
全rootを単純に入れられないことが分かる。上限だけを大きくせず、全体の原子的公開を
保った有界なstage/generation接続が必要である。

`elf.json`は既存Niaの18 ELFに対するPIE、NX stack、RELRO、NOW、非RWX LOADの実検査。
`elf-input-verification.json`でISO構築記録に束縛された7個の元DEBのハッシュと実payloadを
照合し、観測した全18バイナリのハッシュが一致することも確認した。
このELF検査から任意のコンパイラ保護や全OSの安全性を推論しない。

このディレクトリは移行の入力検査であり、Nia package transaction、原本DEBの新たな
署名認証、任意script互換性、Nia-only起動・更新・復旧の受入ではない。
`manifest.json`は自身以外の全証跡ファイルをSHA-256へ束縛する。
