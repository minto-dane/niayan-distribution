# ISO 05/06の再構築比較 — 不一致

同じinput-manifest、独立した新規bootstrapとインストーラー取得、同じ検証済み独自DEBから、2回ともISOの構築は完了した。APTで認証済みのDEBキャッシュは再利用した。ISOのサイズは共に3,640,655,872 bytesだが、SHA-256と実際の`cmp`は不一致だった。結果は`iso-comparison-05-06.json`。

ISO内の`sha256sum.txt`を比較すると、Liveの`filesystem.squashfs`だけが異なった。カーネル、Live initrd、通常・GUIインストーラー、パッケージ一覧は一致した。圧縮前rootの`rsync -anic`と、差のあるファイルを実SquashFSから取り出した結果を保存した。後者の`exit: 2`は対象パスがISOに存在しないことを示し、空の正常ファイルと解釈しない。

調べた差分パスでは、ISO内のAPTの`var/cache/apt/pkgcache.bin`と`srcpkgcache.bin`の内容差を確認した。この時点では、構築終了後の作業用rootで検出した差を中心に調べており、完成SquashFS全体の網羅比較は行っていない。後続の[07/08比較](../reproducibility-07-08/README.ja.md)では完成SquashFSを直接比較し、AppStreamキャッシュの差も特定した。Live package一覧は2,239件で一致し、`unsquashfs -lln`によるファイル一覧・権限・所有者・サイズ・時刻にも差はなかった。通常のroot比較に出るログやビルド用ローカルAPT repositoryは、ISOでは既に空または除去済みだった。

後続レシピは、再生成できるこの2つのAPTキャッシュをlive-build標準の`config/rootfs/excludes`に指定する。APT・live-build・コンポーネントのソースは変更しない。この修正の成功を05/06の結果へ遡って適用しない。05のVM受入成功も、ISOのビット再現性の成功とは別である。

`build-record-06/`は構築後の設定・入力・版・hashの抜粋。参照先のDEB/udebやISO本体はGit外に保管し、ここへ含めない。公開・本番・実機の認定ではない。
