# Native catalogの保存と読み戻し

`Pkg_Catalog_Store.Save`はsealed candidateの正規byte列を既存CASへ保存し、
`Pkg_Selected_Catalog.Fingerprint`と同じアドレスを返す。
`Load`はそのアドレスから全原本を再検査し、catalogとpayload indexを再構築する。
第二の導入済みDBや現在世代のポインターは作らない。

## 永続形式

NIACSEL1は既存fingerprintのpreimageであり、今回hash形式は変更していない。
数値はu64 big-endian、digestは32 byteである。

| byte位置（0起点） | 内容 |
| --- | --- |
| 0–7 | tag長8 |
| 8–15 | ASCII `NIACSEL1` |
| 16–47 | 全payload indexのdigest |
| 48–55 | 原本数1–4096 |
| 56以降 | 各原本の96 byte record |

各recordは元DEB、圧縮controlメンバー、展開済みcontrolファイルのdigestを順に持つ。
元DEBのdigestの昇順で、重複・zero digest・不一致の長さ・末尾余剰を拒否する。
最大frameは393272 byte。Saveは上限付きchunkを既存CAS writerへ渡し、期待hashまで検査する。
保存失敗では返却アドレスをzeroにし、入力candidateは変更しない。

## 原本からの再構築

LoadはCAS読取器のhash・安定性検査を経たframeを検査してから、全元DEBのpayloadと
metadataをnative readerで再観測する。保存frameのcontrol hash、原本集合、payload index、
最終catalog fingerprintを完全照合する。圧縮control hashも最終fingerprintへ含まれる。
元DEBが欠けていれば、過去のmetadataや展開済みblobがCASにあっても成功させない。
空payloadの原本も省略しない。全identity、source版、保護flag、11関係項目のatom/group、
ファイル属性と所有権主張は既存readerを通じて復元する。

失敗では以前の成功catalogとpayloadも含め、両出力を破棄する。
Loadが展開済み内容をCASへ追加する場合はあるが、それはaccepted stateの更新ではない。
期限・UID0拒否・外側3GiB/CPU1core制限を維持する。同期的なCAS hashとlibrary IOには外側timeoutも必要。

## 世代への接続

保存アドレスはgeneration manifestのCatalogへ渡せる既存CAS原本となる。
ただし、供給認証・依存/phase/効果/所有権の検査・CAS pin閉包を完了してからadmissionする必要がある。
`Pkg_Generation_Publisher.Read_Current`の観測は返却前にlockを解放するため、長時間の計画作成後には
同じwriter reservationの下でaccepted generationとBefore_Hashを再照合する。
この保存SDKだけで現在の世代や実行権限を確定させない。

## 検証

合成4原本を保存・再open・再構築し、全metadataとclaimを比較する。
独立したar/tar読取器は単純なregularファイルのみの試験payloadからindexを計算し、
正規frameとCASの実byte列、全metadataを照合する。任意のtarの参照実装とはしない。
20形式不正と、空payload原本欠落、catalog欠落、期限、UID0を通常CIで検査する。
実OS全原本・最大容量・稼働世代admission・保持閉包・実root/bootは未受入である。
