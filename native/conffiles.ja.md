# 設定ファイル宣言と更新判断

`Pkg_Deb_Conffiles`は元DEBからconffiles宣言と対応payloadを読み、`Pkg_Conffile_Transition`は
旧vendor・現在の内容・新vendorの三つを比較する。判断ADR-0095。
実行認可が要求するConfiguration/Side_Effectsの意味を実装する工程で、全効果の完成ではない。

## 元DEBへの束縛

既存Storeの予約を使い、元envelope、control archiveとconffiles原本を再観測する。
宣言がある場合はdata payloadも再観測し、実在する通常ファイル・リンク等の全属性を保持する。
conffiles不在と空fileを区別し、前者だけ宣言hashがzeroになる。
無印でpayloadがない宣言も明示的に残し、空の設定ファイルを捏造しない。
remove-on-upgradeのpathが新payloadにも存在する場合は拒否する。

一行一pathで末尾空白を除去し、remove-on-upgrade後の空白区切りを受ける。
空白だけ/空行・未知flag・重複・非絶対/非正規path・NULを拒否する。countは4096、pathは4096 bytes、
一行は8192 bytesまで。原本サイズは既存control制限の16 MiB以内で、途中失敗はinventory全体を消す。
ファイル名のbyte列を保持し、表示言語に合わせて書き換えない。共有のASCII文字列型やUnicode正規化を使わない。
UID0拒否、既存CASの保持と有限期限を維持し、host pathを開く機能や第二の導入済みDBは追加しない。

## 内容の判断

|状態|判断|
|---|---|
|初回導入・現在fileなし|新vendorを採用|
|現在内容と新vendorが同じ|現在内容を維持|
|vendorが変わらず利用者だけ編集/削除|現在内容または削除状態を維持|
|利用者が変えずvendorだけ変更|新vendorを採用|
|利用者とvendor双方が変更、または初回導入先に別内容|確認要求。自動merge/上書きをしない|
|確認後に現在内容を選択|現在内容を維持し、新vendorの退避を要求|
|確認後に新vendorを選択|新vendorを採用し、存在する旧local内容の退避を要求|
|通常のpackage削除/新packageから設定fileが省略|設定と旧vendor baselineを維持|
|新packageから省略され、local fileもない|現行baselineを解除。世代履歴の保持は別|
|remove-on-upgrade|無変更fileは削除、変更済みfileは内容を退避して削除。履歴は保持|
|明示purge|設定を削除し、baselineを破棄する判断|

Missingは内容が空の通常fileと異なり、読取不能や別inode種をMissingに変換しない。
不明な種別はUnsupportedで出力を消す。Require_Choiceは計算できた未解決判断であり、commitできない。
keep-localでも次回比較のvendor baselineは新vendorへ進む。remove-on-upgradeでも旧baselineは保持する。
宣言が新packageから消えてlocalもない場合の現行baseline解除と、過去世代履歴の回収を混同しない。
識別はNia CASのSHA-256を使う。MD5は試験で上流statusと比較するためだけに使い、認証を代替しない。

判断は内容と退避義務を返し、直接書込まない。呼出側は原本宣言、正確なlocal inode/全属性と保持物、
利用者選択を同じ管理計画へ束縛し、commit直前にも再観測する必要がある。
退避名衝突・リンク追跡・複数所有者・設定生成script、mode/ownerの選択、全root archiveへの反映、
CAS保持履歴と実公開への接続は別の未完工程である。通常tar payloadをこの判断だけで変更しない。

## 上流比較

Debian 13のdpkg 1.22.22を非root・scriptなし・専用root/DBで実行し、126 caseの設定内容、
確認要求、退避内容、次回vendor baselineを比較する。稼働NiaOSの更新backendとしてdpkgを呼ぶ処理ではない。
標準CIに元DEBの宣言検査とこの比較を登録する。
仕様は[Debianの設定ファイル処理](https://www.debian.org/doc/debian-policy/ap-pkg-conffiles.html)と
[Trixie deb-conffiles](https://manpages.debian.org/trixie/dpkg-dev/deb-conffiles.5.en.html)を参照した。
