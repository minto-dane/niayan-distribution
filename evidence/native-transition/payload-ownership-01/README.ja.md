# root世代の論理所有権

対象source subject: `ff7439ce30fecc5c5c16794c59fced58948429d44e8d48914c67fc1effd34738`。
[論理所有権の仕様](../../../native/payload-ownership.ja.md)に従い、元DEBの共有条件と
直接ReplacesをNIAGEN05の保持検査へ接続した。上流原本を改変していない。

固定image、3 GiB/swap0/CPU1/pids128、JOBS=1で四つのAda mainをcompileした。
所有権279、root組立て/実staging199、旧stage1211、旧公開2023、root公開/復旧142 assertion、
実UID0拒否7 assertionが成功した。三つの独立照合とCI登録関連43検査も通過した。
実行は7 invocationで、登録済み75 main全体を再実行したものではない。

11個の人工DEBを使い、採用側からのReplacesの方向・実名・version・architecture、
Multi-Arch:sameの共有内容/属性、有限期限、全path選択と最大添字を検査した。
root fixtureの必要なReplacesを自作controlへ明記した。構造だけ正しい別ownerのrootは
所有権検査で拒否された。staging/公開/復旧と欠損・明示復元は既存の私有CASで確認した。
実OS root、共有ホストデータ、実ディスクを破壊する試験は行っていない。

build-inputs.jsonとinputs-final.jsonは各768ファイル。差分はbuild後に再生成した
ci/test-all.shの登録だけで、Ada/C、fixture、projectと独立照合器のbytesは一致する。
初回のテストdriver構文拒否はcompile-01.logとinitial-test-input.adb.txtへ保持した。
修正後のcompile-02.logとfinal/の全成功を区別する。コンパイラ検査を無効にしていない。
root.tarと二つのmanifestは最終root driverの実成果物で、実原本spanに一致する。
バイナリhash、参照した保持対応ソースの由来、scopeはreport.jsonを参照する。

本番site/効果認可、全DEB効果、特権展開、実サービス、boot、完全置換ISOは未完。
論理所有権の成立だけで本番認定にしない。変更のない全体suite、証明、C sanitizer、
native image、旧カオスcampaign、性能比較は繰り返していない。
