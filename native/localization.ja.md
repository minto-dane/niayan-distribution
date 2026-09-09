# 管理コマンドの多言語対応

[設計判断](../docs/decisions/0004-localized-interface.ja.md)に従い、12コマンドのヘルプ・
引数エラーと、epkg/emgrの成果物操作、emgr_download_ifixの応答を共通の表示層へ接続した。
英語原文と日本語訳115件を管理する。操作要求・認可・元DEBのバイト列は翻訳しない。
製品の対象はDebian 13の全言語であり、現在の完成した翻訳数とは区別する。

## Debian全言語の対象と完了条件

`debian-languages.json`はglibc 2.41-12+deb13u3のSUPPORTEDにある509組のlocale/encodingと、
localechooser 2.112の有効な78選択肢（Cを含む）を保持する。これは「509言語」という
意味ではない。元データの版・SHA-256・参照先を記録し、将来のDebian更新時は差分を
レビューして更新する。インストールマニュアルの翻訳言語だけを対象集合にしない。

全対象のlocale解析・catalog検索を試験する。@latin、@cyrillic、@devanagari等の変種と、
中国語の繁体字・簡体字を区別する。encodingの違いでメッセージ翻訳を複製しない。
全言語を英語文のコピーで埋めて翻訳済みと見せることはしない。

```sh
python3 native/language_coverage.py
make i18n-release-check
```

coverageは各localeを原文・翻訳済み・英語fallbackに分類する。release-checkは
未翻訳があれば非ゼロで終了する。現在は英語・日本語以外の翻訳が未完なので失敗する。
通常のi18n-checkは現在のPO/MOの整合性を検査するもので、全言語完成の代用ではない。
全言語の訳文、フォント、shaping、入力、画面とアクセシビリティの受入は残っている。

対象データの参照: [glibc](https://sources.debian.org/src/glibc/2.41-12%2Bdeb13u3/)、
[localechooserの言語一覧](https://sources.debian.org/src/localechooser/2.112/languagelist/)。

```sh
LANG=ja_JP.UTF-8 native/bin/installp --help
LC_ALL=C native/bin/installp --help
```

有効なLC_ALL/LC_MESSAGESがLANGを上書きする。LANGUAGEの候補順と英語へのfallbackを
扱い、localeデータが未生成の開発環境でも同梱された訳文を利用できる。
Pythonのsetlocale/gettext.installは呼ばず、実行ごとのUIインスタンスを使う。
異なる利用者やスレッドの言語が互いの解析・表示へ混ざらない。

## 翻訳を追加・更新する

`po/ja.po`等の標準POを編集し、以下で抽出・コンパイルする。
ビルド用にGNU gettextが必要で、実CLIはPython標準ライブラリのgettextを使用する。

```sh
python3 native/i18n_catalogs.py --write
make i18n-check
make native-check
```

新しい言語は`po/<language>.po`に追加し、正しいLanguage、Content-Type、Plural-Formsを
持たせる。msgidを独自の翻訳キーへ変えず、文章中の値は`{path}`等の名前付き引数にする。
文脈別の短語は`UI.context`、複数形は`UI.plural`を使う。繰り返しのUIラベルを
別の意味へ使い回さない。再起動のyes/noは`reboot-required`文脈で管理する。

checkはxgettext/msgfmtを実行し、未翻訳、fuzzy、古いキー、プレースホルダー不一致、
非表示制御文字、POT/MOの生成物差分を拒否する。生成日時はPOTの入力にしない。
MOはlittle-endianで生成し、同じ翻訳入力から再現可能にする。翻訳ファイルを実行しない。

## 表示する値とエラー

パッケージ名、版、パス、hash、activation/file-kind識別子は元の値を維持する。
emgrのlabel/value見出しと説明を翻訳する。現在の詳細時刻は元の整数秒であり、
地域別の時刻書式やタイムゾーン変換を実装済みとしない。
Unicode結合文字・ZWNJ/ZWJを維持し、端末制御・bidi override・不正scalarをescapeする。
ASCII端末では表示不能な文字を可視escapeで出し、文字コードの例外で完了後に落ちない。

公開エラーは`diagnostics.py`の固定コードと翻訳文を使う。例えば既存出力は
`NIA-E-EXISTS`、参照不一致は`NIA-E-REFERENCE`で、言語を変えてもコードは変わらない。
任意の内部例外文字列やremote応答をそのまま翻訳キー・端末出力へ渡さない。
SDKの例外は元の診断を維持し、公開画面には分類済みの説明を出す。
I/O失敗を「副作用なし」と表示しない。公開エラーを整理したため、以前の未整備な
Python例外全文に依存するスクリプトとの互換性は保証しない。

## 検証と残る範囲

`test_i18n.py`は実コマンドの言語選択・出力先・終了値・Unicode名の作成、原本保持、
fallback、並行表示、ASCII端末、実MOによる3種の複数形を検査する。
rootコンテナの`check_download_cli.py`も、実HTTPSと署名検証を使って日本語応答を検査する。
通常のTUI/GUI、画面のRTL配置、terminal cell幅、スクリーンリーダー、翻訳者による
追加言語の品質審査、参照応答への完全適合は引き続き受入対象として残る。

参照: [GNU gettextのlocale変数](https://www.gnu.org/software/gettext/manual/html_node/Locale-Environment-Variables)、
[LANGUAGE](https://www.gnu.org/software/gettext/manual/html_node/The-LANGUAGE-variable.html)、
[Python gettext](https://docs.python.org/3.13/library/gettext.html)。
