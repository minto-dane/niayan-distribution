# 管理コマンドの追加調査

2026-09-08。公式のインストール概念、各コマンドの説明、権限管理一覧、診断の
相互参照を確認した。初期一覧に抜けがあったため、採用可否と実装状態を
[機械可読台帳](management-commands.json)に分けて記録した。
全OSコマンドの完全な列挙や、全オプションの適合完了は宣言していない。
名称・商標に関する製品方針に従い、自作コード・説明には中立名称を使う。
調査URLの記録は開発作業領域に保管し、原本のライセンス・既存証跡は改変しない。

| 追加された対象 | Niaでの役割・判断 |
| --- | --- |
| `compare_report` | 導入済み集合と供給集合・別の基準集合との比較。緊急修正も対象 |
| `which_fileset` | 未導入のものを含む供給索引からファイルを検索。導入済み所有権の`lslpp -w`とは異なる |
| `ckprereq` | パッケージの前提条件検査。既存の独立意味検査へ接続 |
| `inulag` | 版・対象に束縛したライセンス提示と同意の管理 |
| `emgr_check_ifixes`, `emgr_download_ifix` | 修正の検索・取得。取得だけで適用しない |
| `autofsinstall` | 未導入コマンドの検索と確認付き導入要求。既定は無効 |
| `mkinstallp` | 通常パッケージの作成。native形式・テンプレート・対話操作の設計が必要 |
| `gencopy` | 選択した導入媒体のコピー。削除・整理の`lppmgr`と役割を分ける |
| `ckauth`, `rmsecattr` | Niaが管理する権限の検査・属性削除に対応し得る。個別採用は未完 |
| `errupdate`, `errmsg` | 診断templateとmessage catalog。必須監査を無効化する操作にはしない |

`inucp`、`inurecv`、`inurest`、`inusave`、`inuumsg`、`sysck`に対応する
内部処理は、既存CAS/WAL・復旧・整合性検査を経由させる。別の公開書込経路にしない。
`rbacqry`はカーネル権限と監査機構に依存するプロセス観測工具であり、単なる
Niaロール照会への別名にはできない。`rbactoldif`もLDAP schemaの対応が必要で、
同意を別プラットフォームの特権として出力しない。

`diag`は主にハードウェア診断・ファームウェア・媒体操作で、Niaのパッケージ検査とは
同じ機能ではない。`lskst`、`setkst`、`setsecconf`、`lspriv`、`tracepriv`、`pvi`や
外部trust/loader工具も、独立したカーネル・外部ソフトウェア側の機能として扱う。
`systemctl`等の外部管理コマンドを包む実装は行わない。

診断系では`oslevel`のrelease集合判定、`errpt`の時系列・filter・詳細表示、
`errclear`の保存期間、`alog`の循環log、`snap`の情報収集を確認した。
Niaのrelease manifest・操作log・証跡へ対応させる設計は未完である。
循環logの上書きや通常logの掃除を、不変の監査証跡の削除と同一視しない。

採用コマンドでも、対応機能の存在・構文・応答・実行・障害復旧は別の受入項目である。
台帳の`planned`や`candidate-unreviewed`を、利用可能なコマンドとして配布しない。
