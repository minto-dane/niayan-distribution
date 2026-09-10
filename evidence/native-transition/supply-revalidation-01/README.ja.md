# 保持TUF metadataの返却前再検証

2026-09-09。開発検証であり、稼働パッケージ管理・実root/boot・本番鍵の認定ではない。
対象source subjectは`fc04dac35a5edcfeee2e9da0b654dece78c257557df5ef5b526a841c4f72a1c8`。
前工程rootは`7959751`。

## 変更

`Repository.revalidate_target`は排他中の正確なcheckpointを新しい上流Updaterへ渡し、
現在時刻でrole署名・版・委譲・target bytesを再検証する。使用した委譲roleと四つの
top-level roleの最短期限を返し、archive intakeの観測期限にも適用する。
追加ネットワーク取得、初期rootへの復帰、第二の永続cacheはない。checkpoint hash・
repository identity・予約の変更、期限到達、時計逆行、共通要求枠とsession期限で失敗する。
元DEBの認証後も有効な供給観測を返すための検査であり、実行許可ではない。

## 実行

新規workspaceで固定native image
`sha256:b626ca976c8ba342df3377e3ad068e29bf45b4c3ad0f7f8927f0551dd09c07dd`の
`make image-check`を実行し、工具173・native153・hardening4・image16の計346試験が成功した。
skipはない。新しい再検証16試験と原本認証接続15試験を含む。
実署名fixtureで各role/委譲の期限、鍵交代後のroot、追加取得なし、保持cacheと予約の変更を検査した。
時計差し替えは試験入力であり、OS時刻は変更していない。

固定開発image
`sha256:0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a`とホストで
source検査を各24工程実行し、すべて成功した。各実行597試験発見・11skipで、skipは実行成功に数えない。
これらのsource検査はnative test suiteを含まないため、nativeの346試験とは区別する。
両reportの実行前後subjectは上記で一致した。工程台帳・code inventory・lintも成功した。
コンテナはnetworkなし・UID1000、全検証を一件ずつ3 GiB/swapなし/CPU1コア分/128プロセスの
実kernel制限内で実行した。制限のreadbackは各実行logに含む。

`workspace-inputs.json`の全入力を元repoと新規コピーで照合した。実行後のroot引継ぎ文書2件の
変更だけを`handoff-only-changes.json`へ分離し、八repoのsource subjectが不変であることを確認した。
七コンポーネントのdocs/engineering以外の全入力と、七つの数学的入力集合は不変である。
Ada build/main実行・再現性・形式証明を重複実行していない。新しいPython試験を形式証明と数えない。

`qualify.py`と`retain.py`は当該開発環境で使用した記録用工具である。
移植可能な標準検査入口は`distribution/Makefile`と`assurance/ci/run-engineering-checks.py`を使う。
`SHA256SUMS`は記録の完全性確認用であり、製品の信頼anchorではない。

## 残る条件

保持metadataを現在時刻で検査しても、remoteでの新たな失効・policy更新を取得したことにはならない。
本番のpolicy/key配備、rollbackに耐えるtrust floorと時刻、認証原本のnative CAS・保持閉包・
公開計画への実行時の束縛は未完。全DEB phase/効果/所有権、実起動切替、完全置換ISO、
全言語翻訳も未完である。公開download CLIのroot試験や公式archiveの再取得は今回は実行していない。
