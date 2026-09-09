# 世代image候補の検証: tar直接入力は未採用

2026-09-09。root `aaeee76`、pkgcore `b7eed54`を基準にした合成入力の実験。
`report.json`は実験の判定、`probes/comparison.json`は原本とimageの属性比較である。
これは本番backend、image検証SDK、全元DEB、kernel mount、bootの受入ではない。

## 実行と結果

固定Ada開発imageに、固定snapshotから未改変erofs-utils `1.8.6-1`を追加した。
`Containerfile`、`image-id`、`toolchain.json`に構築入力と実版を保存した。
パッケージ取得は開発builderの内部だけで、NiaOSへ別の管理器を導入していない。
`builder.log`の最初のCLI失敗も保存し、修正後の構築は`builder-02.log`に記録した。

11個の既存payload合成DEBと、追加4個の小さなtarを用いた。
19回のmkfsで17個のimageを生成し、その17個は`fsck.erofs --extract IMAGE`を通過した。
`=DIR`を付けていないため、fsckはhost filesystemへ展開していない。
全構築は非特権UID1000、networkなし、worker1で行った。
外側は`dev/run-limited.sh`のmemory3GiB・swap0・CPU1core・pids128である。

独立した実験reader `read_erofs.py`で非圧縮extended inodeとdirectoryを読み、
`compare.py`でPython tarfileの原本観測と比較した。readerはこの有限の合成入力に
限定した実験用で、任意imageの構文検証器ではない。assertionを無効化して使わない。

- 基本USTARの9 entryでは、通常内容、全permission bit、UID/GID、既出targetへの
  hardlink identity、symlink bytes、character/block device番号、FIFOを照合した。
- 長いGNU/PAX名と多言語名の試験では、名前と通常内容が一致した。
- `basic`の前方hardlinkと`gnu-numeric`はmkfsが失敗した。
- `attributes`はuser xattrとcapabilityのraw bytesを保持したが、access ACLを保持しなかった。
  capabilityの値は観測用で、有効な実行権限を付与した試験ではない。
- `1700000000.25`は`1700000000秒+25ns`となった。
  `-1.25`は`-1秒+25ns`、`-0.000000001`は`0秒+1ns`となった。
  原本の正しい値はそれぞれ`1700000000秒+250000000ns`、`-2秒+750000000ns`、
  `-1秒+999999999ns`である。比較にはDecimalを使いfloat丸めを避けた。
- 9桁小数部の正時刻と負の整数PAX時刻は当該入力で一致した。
- 独立のatime/ctime/btimeとinode flagsは試験image profileに独立の格納欄がない。
  これを個別の原本値が実現された証拠にしない。
- rootや親を明示しない入力では暗黙directoryがmode0777となった。

追加4入力はTZ=UTCとPacific/Honolulu、出力名a/bで構築し、各組のimage bytesが一致した。
これは同じbuilderでの再現性であり、独立toolchain buildや時刻属性の正しさではない。
入力tarのmtimeを変えた試験でもない。

## 失敗出力と保存時の修正

失敗した2出力は論理2TiBの疎ファイルを残した。割当量はそれぞれ4096/0 bytesである。
最初の通常コピーが疎領域を展開し始めたため停止し、作成途中の15,464,833,024 bytesを
削除した。開発領域の空き容量は回復した。元の失敗出力は変更していない。
最終証跡では2出力そのものを除外し、`failed-output-stats.json`と失敗logを保存した。
成功出力を含む保存対象は個別に1MiB以下と確認してからコピーした。
未検査の失敗成果物を再帰コピーや全内容hashへ渡さない。

## 再確認

保存済みimageの比較は次で実行できる。実験readerに第三者のimageを与えない。

```sh
sh dev/run-limited.sh python3 distribution/evidence/native-transition/generation-image-01/compare.py
```

構築時の正確な引数は`probes/results.json`と`probes/extra-results.json`にある。
`probe.py`、`probe_extra.py`は当時の隔離container内の`/work`、`/fixtures`を使う。
`run.py`には当時のlocal image/cache/workspaceの絶対パスを記録しているため、
別のcheckoutでそのまま使える汎用builderではない。新しい場所では固定開発imageの
再構築とmount対応の明示が必要になる。失敗出力を成功成果物として収集しない。

生成器を採用する前には版付きの属性契約、全所有権、認可、全DEB効果、mutable data、
実mount/bootと障害復旧を閉じる必要がある。今回runtimeや共有contractは変更していない。
過去のcompile/proofを今回の新たなruntime検証として数えない。
