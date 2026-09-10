# 設定候補と選択の受入

対象source subject: `ada07d0d7094d368868fb7a829276f8bab6e8e5559306f49fb8066a05257d4b0`。

最終判定は`test-06.log`。Debian 13固定containerで強制compileし、非root・私有root/CAS・
scriptなし元DEBを使う154 assertionが成功した。377 compile入力と22 fixture入力を実workspaceと照合した。
原本/宣言とlocalへの束縛、初期期限、両選択と次回vendor原本、通常削除/purge/宣言付き削除/省略、
退避衝突/後発作成、別候補/閉包、選択待ち中の編集、保持原本欠損と非再作成を確認した。

初回はtestのByte演算可視性、次はmediaへの相対path指定で停止した。修正後は新規CAS/rootを使用した。
`test-05.log`はキャッシュされた旧152 assertionで、最終sourceの受入にしない。
固定再現性時刻のALIを含むcacheを使う場合は、対象mainを強制再compileして入力を照合する。
最終runは154 assertionへ増えたことも確認した。失敗/途中ログを上書きしていない。

source構造/link/lint/licenseと生成CI検査も成功。数学的入力/共有vendorは不変で、
全suite/証明/旧カオスやVMは反復していない。上限3 GiB/swap0/CPU1/pids128、全job終了済み。
実DEB導入や公開コマンドへの配備、利用者の認証同意や本番認定は行っていない。

特権属性observer、全managed認可と認証UI、全属性/全namespaceの選択、durable reader/recovery、
世代保持と実root/boot公開、完全置換ISO、全言語翻訳等は未完。
秘密鍵、実設定、CAS、ELF、core dumpやVM diskはこの証跡へ含めない。
