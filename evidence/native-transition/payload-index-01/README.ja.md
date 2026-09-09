# 原本claim索引の実行検証

2026-09-09。`Pkg_Payload_Index`のprivateな原本・claim索引を検証した。
これは選択された全catalogの完全性、実効所有権、実filesystem生成や導入認可の受入ではない。
[実装境界](../../../native/payload-index.ja.md)とADR-0067を参照。

## 結果

- 固定Debian 13開発imageでpkgcore全source・4アプリ・21 Ada mainを実コンパイルした。
  全登録試験が成功し、新規driverは449 assertions、既存payloadは814 assertionsである。
- 追加3合成DEBの再生成byteとmanifestが一致した。
- 11既存合成DEBと3追加DEBの14原本・35 claim・28 pathを、独立tar/CAS oracleと
  Pythonのcanonical hash計算で照合した。逆順でも同じhashになった。
- 保存済み13元DEBと大型合成DEBの14原本・2904 claim・2493 pathも同様に照合した。
  展開tar合計166,123,520 bytes。順方向・逆方向で同じhashである。
- 当該元DEB集合を一つのnative processで索引化した最大RSSは順方向20,568KiB、
  逆方向20,624KiBだった。対象入力の測定であり、4096原本・524288 claim・256MiB名の
  最大容量を実負荷で資格化した結果ではない。
- 異なるbuild path・入力mtime・TZで25実行ファイルのbytesが一致した。
  503入力ファイルをcheckout・通常・独立・sanitizedコピーで照合した。
- 25 ELFについてPIE、non-executable stack、RELRO、BINDNOW、RWX LOAD不在を確認した。
- 使い捨てroot containerでは世代stage/publication・payload・indexの拒否試験を実行した。
  driver assertionsはそれぞれ1100、34、3、6。SDKのUID0拒否を解除した試験ではない。
- ASan/UBSanをリンクした新driverでも449 assertionsが成功した。
  C境界とallocator/library-call interceptionの範囲であり、Adaと上流library本体は
  計測していない。leak検査は無効で、この結果を全メモリ安全性の証明にしない。
- 7repoのSPARK入力集合とhashは不変である。新runtimeはSPARK対象外。
  数学的入力が不変の既存proofは重複実行していない。

最終ソース24工程も成功し、その実行前後subjectは
`d8d464830a283c50c37cfc7c907db77ed80c0a90d90c6f3bce7b20dddca1bd77`で一致した。

全工程は一度に一つずつ、`dev/run-limited.sh`のmemory3GiB・swap0・CPU1core・pids128で
実行した。native containerはnetworkなし、通常UID1000、拒否試験だけUID0である。
固定imageは`0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a`。
上流source・共有runtime・共有contractを改変していない。

## 比較対象と読み方

`accepted-build-test.log`、`root-probe.log`、`sanitized.log`に実行結果、
`reproducibility.json`、`elf.json`、`input-comparison.json`に独立build比較を保持する。
`retained-*-forward-oracle.json`と`retained-*-reverse-oracle.json`は原本tar/CASと索引の比較、
`retained-*/resources.json`は各原本payload子processの測定である。
集合全体の索引processは`retained-*-*-resources.json`に別々に測定した。

`compare_payload_index.py`は`compare_deb_payload.py`で各元DEB・tar・全CAS hashを
独立に照合してから、別実装のcanonical hashを計算する。native同士の比較だけではない。
hardlink headerとinodeの差、共有directoryの差、同じ内容の別owner、非directory祖先、
暗黙parent、Unicode、原本inventoryの破棄、期限・未seal・境界外を検査した。

CASと大きな元DEBそのものはこの証跡へ重複収録しない。原本hashと取得由来は
`original-media-inputs.json`、大型合成入力は`large-input.json`、個別観測は保存したlogを使う。
比較を再実行する場合は`run-corpus.py`で、同じhashの入力と新しいprivate CASを用意する。
`run-container.py`は当時のlocal cache/workspaceの絶対パスを含む実行記録であり、
他のcheckoutでそのまま動く汎用builderではない。固定環境の構築はdev/READMEに従う。

## 残る範囲

このindexは渡された原本集合の観測に限る。認可されたresolver集合との一致、package
identity/版/architecture、Replaces/Multi-Arch、alias、実効owner選択、構成と全DEB効果、
CAS pin閉包、稼働catalog/guard、rootの作成と実mount/boot・復旧は未完。
最大容量・実全OS集合・長時間運用・電源断の受入でもない。実言語翻訳とUI受入も別工程である。
