# ISO 09の対応ソース

通常収集1,414組と署名用カーネルsourceの補完1組、合計1,415組・4,667ファイル（8,524,077,623 bytes）を取得した。ホストへのコピー後、[検査](source-verification.json)で全source archive・DSCの版・サイズ・SHA-256を再照合し、成功した。

- [通常収集](report.json): Live一覧2,239パッケージの全版にbinary対応あり。通常99件・GUI175件の内蔵installer inventoryも対応付けた。Built-Using・Static-Built-Usingを含む。
- [署名用カーネルの補完](signed-kernel-sources/report.json): Linux本体6.12.107-1は通常収集にあり、インストーラーの6.12.94-1を追加した。udebで省略された参照を署名用source内の正式なcontrolから読み、接尾辞で版を推測しない。
- [ファイルmanifest](source-files-manifest.json): source archiveとDSC等4,667ファイルのパス・サイズ・SHA-256。

1,407組は固定snapshotの署名付きAPT索引で取得し、8組は記録された独自native source packageを検証して保管した。古い内蔵udebのcontrolを得るためのdebsnap HTTPS取得は、APTアーカイブ署名検証と区別する。非自由firmwareのsource packageには可読なfirmwareソースが含まれない場合がある。

通常収集と補完の工具は別々に固定して実行し、自己hash・base report・ISO・入力manifestに結び付けた。初回のarchitecture指定による停止は[別記録](../../source-collection-attempt-01/README.ja.md)に保存している。コピー時にはDistroboxでVMのAPT用groupを設定できず、所有者・groupをコピー先に合わせる設定で同期した。両ログを残し、内容の一致はその後の独立した全ファイル照合で確認した。

このGitディレクトリは小さな記録と工具だけを含む。report内のsource archiveパスは、Git外の完全な`corresponding-sources/`保管物を指す。補完report内のパスはその`signed-kernel-sources/`からの相対パスである。APT索引・取得したudeb等の補助ファイルも完全保管物にある。これらを除いたGitの記録だけを対応ソース一式として配布しない。
