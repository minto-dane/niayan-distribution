# Native catalogのCAS保持閉包

`Pkg_Catalog_Retention`は、元DEBから再観測したcatalogに必要なCASオブジェクトを
一つの正規マニフェストへ束縛し、既存のimmutable pinで固定する。
導入済み状態は従来のaccepted plan/catalogが正本であり、この一覧は第二の管理DBではない。

## 対象と形式

一覧はcatalogそのもの、全元DEB、圧縮control/dataメンバー、展開data tar、
control内の全regularファイル、payloadの内容・symlink文字列・xattr・ACLを含む。
空payloadの原本、空ファイル、未知のregular controlファイルも残す。
同じ内容の参照はdigestで重複除去する。hardlinkの内容は原本内の対象と共有するが、
各headerの属性記録は既存payload indexで維持する。
元DEB内のversion情報・extensionは原本全体で保持する。別途任意にstageした未使用メンバー、
メモリ内のcontrol展開buffer、CAS全体の無関係なobjectは本profileの一覧に含めない。

| byte位置（0起点） | 内容 |
| --- | --- |
| 0–7 | ASCII `NIACLOS1` |
| 8–39 | native catalog digest |
| 40–71 | payload index fingerprint |
| 72–79 | unique object数、u64 big-endian |
| 80以降 | 厳密なdigest昇順の32 byte record |

上限は`1 + 4096 × (4 + 64) + 3 × 524288 = 1851393` objects、
最大59244656 byte。一覧はstreamでCASへ保存し、期待hashとbyte数を照合する。
このマニフェスト自身はpinの参照先であり、自己参照を一覧へ入れない。
payload fingerprintはcatalogとの束縛であって、そのhashのCASファイルが存在すると仮定しない。

## 保存・検査・pin

`Prepare`は`Pkg_Catalog_Store.Load`で全原本とpayloadを再検査する。
さらにcontrolの全regular内容を再観測し、全参照先の存在・hashを検査してから一覧を保存する。
派生objectが失われている場合には、この明示的な候補構築で再生成することがある。
原本欠落をcacheで代替することはできない。

`Verify`は一覧のhash・形式・全掲載objectを先に検査する。
この時点では再生成しないため、復旧可能なcache欠落も欠落として返す。
その後に原本から正確な集合を再構築し、期待するマニフェストhashと完全一致を要求する。
単に各掲載hashが存在するだけでは成功しない。単独の省略・余分なobjectも拒否する。
再構築により正しい候補一覧や派生物がCASに残る場合はあるが、pinやaccepted stateは変更しない。

`Pin`はPrepare後に既存`MC_Store.Pin`へ渡す。`Verify_Pin`はpinの一致を先に確認し、
Verifyで全内容を検査する。既存のstage/publication transactionとは異なる新規identityを使う。
[native世代](generation-retention.ja.md)では直接Pinを重ねず、既存世代manifest pinから閉包を参照する。
同一identity/対象の再試行は可能だが、異なる型・対象に束縛済みのpinを上書きしない。
失敗時のPrepare/Pin出力はzero。期限切れや不確定なpin書込では、永続pinが既に存在する場合がある。
未実行と判断せず、同じidentity/catalogで再試行・検査する。

全APIはUID0を拒否し、呼出し中は既存の開いたCASの予約を維持する。
同期hash・library IOには外側timeoutと3GiB/CPU1coreの資源制限も必要。
上限の数値だけを最大容量の受入としない。store ownerやrootによる予約外の改変への証明ではない。

## 検証と未完範囲

既存catalog保存driverを拡張し、4原本の21 objectsと、圧縮control/data・script内容・
七payload種・非空xattr/ACLを持つ追加原本の15 objectsを照合する。
21通りの単独省略、21通りの掲載object欠落、14種類のその他形式/集合不正、
実byte破損、pinの衝突/欠落/再open、明示的再構築、期限、UID0を検査する。
独立Python readerは元DEBの内容から全member集合とマニフェストbyte列・pinを再計算する。
追加原本のpayload fingerprintは保存catalogとの相互束縛を確認する範囲で、
このreader自身が全payload indexを再計算したとは数えない。
試験内のscriptを実行せず、deviceやリンクをhostへ展開しない。

これはcatalog由来の保持閉包であり、世代全体の保持・削除認可ではない。
accepted plan・世代descriptor/manifest・batch plan/receipt・生成効果・認証・復旧起動・
履歴世代を含む全root集合の完全な列挙、保持期間と安全なGCは引き続き必要である。
このAPIはobjectもpinも削除しない。独立したbackup削除方針をCASの削除許可に読み替えない。
供給認証・本番の同一予約でのadmission・実行phase・所有権・全DEB効果・実root/bootと
完全置換ISOは、この検証だけで完成扱いにしない。
