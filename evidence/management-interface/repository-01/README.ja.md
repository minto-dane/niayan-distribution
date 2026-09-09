# 共有供給認証と緊急修正取得の開発検証

Debian 13の固定コンテナでnative 91件、hardening 4件、image 16件が成功した。
実公開コマンドの4項目は別の使い捨てrootコンテナで成功した。ネットワークは
loopbackだけとし、実HTTPS・一時CA・実TUF署名・root所有policyで原本を取得した。
試験時のメモリ3 GiB・swapなし・CPU 1コア・128プロセスのkernel制限はログに記録した。

暗号署名・委譲・鍵交代・期限・古いmetadataの拒否、排他、原子的checkpointと
fsync/replace失敗、参照hash、既存出力保護、policy再読を検査した。
対象source subject、入力ハッシュと結果の正本はreport.json、ソース検査はsource-check/。
試験依存はtest-packages.txtと固定Containerfileに記録する。

初回コンテナ試験のGit不足とHTTPS試験の未処理TLS例外は修正し、失敗ログも保持した。
依存追加によるcomponent CIの生成物不一致も、正本generatorで再生成し、初回失敗を保持した。
CA更新時のbundleに関するrehash警告は通常の診断であり、取得時のTLS検証は実際に成功した。
試験秘密鍵・CAはコンテナや一時領域でのみ使用し、証跡には含めない。

これは人工DEB・人工参照を使った供給経路の検証である。契約内容の意味検証、
Debian archive chain、独立trust floor、稼働catalog・適用・削除・保留、応答の参照適合、
TUI、新ISOと実電源断復旧は未受入。新しい形式証明やVM認定を行った記録ではない。
