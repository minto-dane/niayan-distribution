# 自作配布メタデータのBSD-3-Clause表記

source subject: `3946b76aa30756cd060789af6317816e36a75993684aa0d4d608829bebbb636a`。
ADR-0088の追補。assurance/pkgcore/statecore/controlcore/configcore/resolvercoreのRPM定義に残っていた
旧MIT License fieldをBSD-3-Clauseへ変更し、現行説明LICENSING.mdと過去のMIT許諾文も同梱対象へ追加した。
第三者の原本metadataや旧証跡、既存の著作権表記と許諾文は変更していない。RPM実buildは未実施である。

旧検査器はソースのSPDXを確認していたが、RPM License fieldを見逃していた。
検査を拡張すると実6定義が拒否され、メタデータ修正後に成功した。修正前の6原本とSHA-256を保持する。
自作DEBのcopyright fieldも全定義を確認し、既存2パッケージの必須copyrightが欠ける場合も拒否する。
最終検査器はcheck-licenses.py、実行結果はlicense-check-final.json。root-input.jsonはそのhashを記録する。
rootのdev工具はengineering source subjectに含まれないため、これを別に明示した。

構造/参照/lint/生成CIも成功した。runtime/数学的入力は不変で、C/Adaビルド・VM・形式証明は反復しない。
本番認定・RPM認定・GitHub公開を意味しない。Debian完全置換等の既存未完条件はSTATUSに保持する。
