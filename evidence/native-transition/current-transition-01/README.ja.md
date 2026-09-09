# 確定済み世代に束縛した更新計画の検証

`Read_Current_Transition`は、現在のdescriptorと候補catalog/保持閉包を
同じpublication/root/CAS予約内で検査し、通常更新の結果をNIAUPD01へ束縛する。
仕様は`distribution/native/current-transition.ja.md`、判断はADR-0075。
本番admission、DEBの物理適用、実起動、完全置換の認定ではない。

## 到達点と未完の検査

独立した新規ソースコピーで全18アプリとpkgcoreの25 mainを構築し、
単独CIと独立reader、root拒否8本、ASan/UBSanリンク下の公開試験を実行した。
通常公開試験は1361 assertions。18回の更新観測、四つのBinding、
候補閉包自身/memberの8欠落を独立readerで照合した。
基準世代の保持欠落と既存復旧行列も維持する。
追加した拒否試験は不成立の依存、誤った基準/保持hash/root、期限、排他、architecture policyを含む。
root拒否の公開driverは40 assertions。変更runtimeはSPARK対象外で、
既存7repoの数学的入力が不変であることだけを照合した。
sanitizerはC境界とallocator/library呼出しの検査であり、Ada・上流library本体は非計測、leak検査は無効。

全体の標準`make check private-dbus JOBS=1`は、engineering単体試験の
安全ガードがホストの利用可能メモリ不足を検知し、Ada実行前に失敗した。
開始条件はsession上限2 GiBとreserve 2 GiBの合計4 GiB。
検査を省略して全体PASSとはせず、上限・reserve・guardは変更していない。
通常ビルドは別に実行できるが、全71 mainと全体検査の認定は保留である。
実際の検査結果・再現性・source subjectは`report.json`と各実行ログを正本とする。

## 再現用資料

`reference-snapshot/`には診断で実際に使った小さい合成root、state、CAS、pin、原本を保持する。
`tree/version`は合成効果であり、DEB payloadの適用ではない。
次の独立readerは採用バイナリによる通常CIの結果とも完全一致することを確認する。

```sh
python3 -B readers/compare_current_catalog.py \
  --root reference-snapshot/root --state reference-snapshot/state \
  --cas reference-snapshot/cas --bank reference-snapshot/bank \
  --media reference-snapshot/media --native reference-snapshot/native.log \
  --output /tmp/nia-current-transition-oracle.json
```

`attempts/`は再起動後の古いPodman runroot拒否と、メモリ不足で失敗した標準検査を保持する。
再起動後は既存storageと固定imageを保持し、今回専用の新しいrunroot/tmpdirを使用した。
すべての重い実行は`dev/run-limited.sh`で一つずつ実行し、memory 3 GiB、swapなし、
CPU一コア分、128 processes、JOBS=1を維持した。ユーザーのアプリは停止していない。

全体検査の再開前に実際のメモリ余裕を確認する。未成功の全体検査を既存世代の
成功証跡で置き換えない。本番認証との接続、全phase/所有権/効果、実root/boot、
全履歴の保持とGC、完全置換ISO、全言語翻訳は引き続き未完である。
