# Nia OS の単一供給基盤 — Debian 14 Forky / DEB

状態: Nia OS 0.1 開発対象として選択。独立設計審査・本番資格化は未完了。
調査基準日: 2026-09-07。製品と供給元を混同しない。

## 結論

Nia OS は Debian 14 **Forky** の内容固定スナップショットを、amd64/all のバイナリ・ソース供給元として使う。Focal は Debian 14 の名前ではない。単一対象を守り、testing という動く別名をライブホストが追い続ける方式にはしない。旧 Leap/SLES/Alma のプロファイルは現行の選択肢ではない。

Nia OS は Debian のサポート対象製品そのものではない。Debian から継承するのは、検査した成果物と、それを使うために必要な ABI/ファイル配置/ライブラリ関係である。APT、dpkg の状態DB、RPMDB、Zypperをホストの管理権威に残すことは要件から除外した。

## 比較の基準

| 項目 | Debian / DEB | openSUSE / RPM | AlmaLinux / RPM |
|---|---|---|---|
| 機械可読な依存 | Depends/Pre-Depends/Breaks/Conflicts/Provides/Multi-Arch、Policyが詳細 | Requires/Provides、rich dependencies、段階flags | RPM同系統。配布方針はAlma側 |
| ファイル属性 | data.tar の型・mode・UID/GID・link・任意拡張とcontrolを統合して得る | ヘッダーにfile digest/flags/owner/group/capabilities等を集中保持 | RPMと同じ長所 |
| 設定 | conffilesは所有・保存方針の手掛かり。意味検査は別 | config/noreplaceは手掛かり。意味検査は別 | 同左 |
| 配布の認証 | InRelease→Packages→DEBのハッシュ鎖。通常は個々のDEB署名ではない | repomdとRPM署名。両方の供給者・鮮度・関係を確認 | 同左 |
| 再現性 | 配布済みの公式DEBを再構築する基盤とForkyへの移行ゲート | Factoryにもbit-reproducibleの取り組み。署名等の違いに留意 | SBOM・出所記録の基盤。再構築一致の証明とは別 |
| 独自管理器に必要な追加 | 効果契約、完全な入力・稼働観測、データ移行、信頼更新 | 同じ。RPMが代行していた処理を省くと同じ穴が生じる | 同左 |

RPMの属性モデルが弱いとは判断していない。Niaは自分のcatalogを持つので、認証したDEBのpayloadから同等に必要な基本属性を導出できる。動的ユーザー、capability、SELinux/AppArmor、生成物等は両形式とも専用契約が必要である。標準の弱いmd5sumsだけに依存せず、元の認証済みDEBからSHA-256 inventoryを作る。

今回の優先順位は、①既存配布バイナリと対応ソースの照合、②再現性の観測資産、③独立した意味検査を作る資料、④従来管理器を継承しない構成、⑤開発中製品としての時間軸、である。RPMのメタデータ量だけを理由に供給基盤を固定する合理性は小さくなったため、Debianへ変更する。

詳細な対応は[metadata比較](metadata-comparison.ja.md)を参照。

## 再現性について、保証しないこと

2026年5月の移行方針は、新しい非再現パッケージと再現性の後退をtestingへ入れない方向であり、例外もある。「全アーキテクチャ・全パッケージ・非free firmwareまで既に完全再現済み」ではない。Niaはパッケージ名や公開ダッシュボードの緑表示を、そのまま実行許可へ変換しない。

対象DEBのSHA-256、source inventory、.buildinfo、実際の再構築出力を照合し、独立した信頼登録にある観測者の証拠を扱う。コード中の二者署名検査は、実際の第三者再構築サービスが既にNia形式で証拠を供給していることを意味しない。必要な公開証拠がなければ、外部の再構築者との接続・証拠発行が必要になる。

ソース自体の欠陥、コンパイラの共通故障、同一組織が別名を使うこと、署名鍵侵害は、再現一致だけでは排除できない。主なOSSは厳格経路、非free firmware/NVIDIA等は明示的な別の例外分類とする。例外を「再現済み」と表示しない。現行compose工具はmain以外を拒否する。

## testingのリスク

Debian自身が、testingのセキュリティ修正には移行遅延があり、stableの安全運用支援と同等ではないと注意している。「他OSよりtestingの方が安定」という一般順位の証拠はない。

よって本番はrolling testingを追わず、intake→正確な集合の固定→検査→段階配布を行う。修正遅延を測り、重要修正の期限を管理し、供給元がまだ配布していない修正版が必要な場合は限定した自前ビルド又は提供者協力が必要になる。「全パッケージを自分でビルドしない」と「一度も緊急ビルドが要らない」は違う。

Forkyがstableになっても自動的にNiaが本番認定になるわけではない。Nia側の通常起動、復旧、MAC、構成・データ契約、現場試験を別に認定する。

## GPU / 商用支援のトレードオフ

調査したCUDA 13.3表のDebian対象は12/13で、14やNia OSの公式認定ではない。GPU機能の採用試験はkernel/module/userspace/compiler/CUDA/構成の正確な組合せに対して必要である。旧NVIDIA意味検査器は資産として維持するが、この変更だけで全版の観測器が完成したことにはならない。

現時点で商用の長期支援とCUDAの公称対象を最優先する別条件ならAlma等の評価は変わる。ただし、今回の「まだ開発中の独自OS、管理器互換性不要、検証資産優先」という条件ではForkyを選ぶ。複数基盤を同時に支援しない。

## 一次資料

- Debian Forky: https://www.debian.org/releases/forky/
- Debian security FAQ: https://www.debian.org/security/faq
- 2026-05 reproducibility policy report: https://reproducible-builds.org/reports/2026-05/
- Official archive rebuild status: https://reproduce.debian.net/
- Debian binary relationships: https://www.debian.org/doc/debian-policy/ch-relationships.html
- DEB format: https://manpages.debian.org/unstable/dpkg-dev/deb.5.en.html
- Binary control: https://manpages.debian.org/unstable/dpkg-dev/deb-control.5.en.html
- Buildinfo: https://manpages.debian.org/unstable/dpkg-dev/deb-buildinfo.5.en.html
- Archive authentication: https://manpages.debian.org/unstable/apt/apt-secure.8.en.html
- RPM tags: https://rpm.org/docs/4.20.x/manual/tags.html
- openSUSE reproducibility: https://news.opensuse.org/2024/04/18/factory-bit-reproducible-builds/
- AlmaLinux SBOM: https://almalinux.org/sbom/
- CUDA support table: https://docs.nvidia.com/cuda/cuda-installation-guide-linux/
