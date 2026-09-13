# 実環境での悪用に関する機関報告

`Authority_Reports_Wild_Exploitation`は「信頼する機関が、実環境での悪用を確認したと報告している」
ことを表す。旧Exploited/Active_Exploitという曖昧なfieldを置換した。
「この端末が攻撃された」「この端末が侵害された」「この端末で当該CVEが悪用可能」の意味を持たせない。

CISA KEVはこの種の情報源の一つであり、実環境で悪用された脆弱性を優先順位付けの入力にするcatalogである。
報告元authority、取得した原本/recordの識別子、報告日と取り込み時刻、対象CVE、ローカルの適用判定を
別々に保持する。KEV dateAddedはcatalogへの掲載日で、最初の攻撃日やこの端末の検知日時ではない。
情報源の認証はTLS等と信頼方針に基づき、原本にないデジタル署名があるとは仮定しない。

Ada advisoryはpositiveな報告に認証済みsource/record/dateを必須とし、kernel保守もsourceが
不明なpositive情報から緊急判断を出さない。falseは今回の観測に該当報告がないという意味であり、
未悪用・無脆弱性の証明ではない。未取得、期限切れ、未掲載、明示的な訂正は収集器で区別し、
通信失敗で過去のpositive報告を消したり、修正優先度を下げたりしない。

実端末の侵害は別のincident/detection情報とし、node/boot/観測元/時刻/対象を束縛する。
脅威機関の報告だけでは端末侵害として隔離しない。影響範囲と修正済みbuild、stable/backport対応を
別に判断し、CVE未掲載の通常bug fixも供給更新から除外しない。

現在は意味とAda側の必須入力を実装した段階で、CISA KEVの本番取得/正規化/信頼providerと
多言語の実表示は未接続。原本hashやBooleanだけで外部機関を認証したことにはならない。

参照: [CISA KEV catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)、
[Linux CVE方針](https://www.kernel.org/doc/html/next/process/cve.html)（2026-09-12確認）。
