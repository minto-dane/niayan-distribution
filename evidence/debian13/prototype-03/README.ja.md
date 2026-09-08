# Debian 13試作ISO 03の実行記録

2026-09-08。対象ISOのSHA-256は`2c9ef21212d0556c3eafdeacabc3839f7adf6b127a01c8436e00476b24c5110a`。最終レシピの受入とは別の試作記録。

| 試験 | 結果 |
| --- | --- |
| `live-bios-05` | BIOS起動、KDE Waylandで実キーボード入力から「日本語」を保存、通常電源断に成功 |
| `live-uefi-network-01` | UEFI起動、通常HTTPSミラーの署名付きAPT索引取得に成功 |
| `live-secure-boot-01` | OVMFのSecure Boot有効状態で起動に成功 |
| `install-uefi-03` | ネットワークなしで新規仮想ディスクへ導入し、UEFI再起動に成功 |
| `install-bios-network-01` | BIOS導入と起動は完了したが、ミラー未登録を検査で検出。全体は失敗 |
| `installer-network-inspect-01` | 上記の診断実行。成功受入として扱わない |

オンライン試験のインストーラー記録は`apt-setup/use_mirror=true`を保持しているが、ミラー設定用モジュールが存在しなかった。live-buildの既定除外にある`apt-mirror-setup`を、後続レシピでは公式udebの標準追加入力として取得する。上流コードの編集は行わない。

試作03の構築ログには、ビルド用の最小環境でCA証明書が不足したHTTPS取得の警告も残る。Live本体のHTTPS試験成功を、このビルド工程の成功へ読み替えない。後続レシピではdebootstrapの正式なinclude指定と新規bootstrapで修正する。

初期のBIOS試験では、デスクトップ起動待ち、入力フォーカス、シリアルの改行処理、Live終了時のメディア取り出し確認への対応を修正した。ここに保存した`live-bios-05`は、それらの修正後に最初から実行した成功記録である。

各reportは実際のISO・工具hashと実行範囲を保持する。オフライン導入実行中に診断工具を更新したため、その親reportと再起動reportの工具hashは異なる。最終版の一括受入では工具を固定して再実行する。

ISO、DEB、initrd、試験ディスクはGit外に置く。`build-record.json`内の完全なステージファイル一覧は外部のビルド記録を指し、この小さな証跡ディレクトリへ全ペイロードを複製したという意味ではない。ログの圧縮はgzipのmtimeを0に固定した。公開された試験用資格情報は専用VMだけで使用する。
