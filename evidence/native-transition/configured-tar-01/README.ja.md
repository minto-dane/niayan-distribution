# 設定entryのPAX出力と相互読戻し

対象subject: `74b1d80006cd2fb2638b165826ba4407a28a0a15cc6290742bc7dc3ab3933d22`。本番認定ではない。

Pkg_Tar_Outputは、raw名、数値owner/permission、全signed nanosecond時刻と拡張fieldから
通常fileのPAX/header prefixを生成する。Add_Xattrはraw名/値をLIBARCHIVE形式へ変換する。
新しいreader側の検査はBINARY、全signed時刻、encoded名とbase64の境界を扱う。
既存のsource xattr/ACL/flag・実適用方針を無条件に作り替えるものではない。

固定Debian 13 image、UID 1000、networkなし、3 GiB/swap0/CPU1/pids128で対象2 mainを
`gprbuild -f -j1`により強制compileした。最終test-04.logは出力79 assertionと既存payload814 assertion成功。
生成したnormal/full-rangeのtarを独立PythonのDecimal/byte比較で読み、scriptなしのDEBへ包んだ。
既存native payload readerを各26 assertionで通し、内容/原本hash、全4時刻、raw名、UID/GID/mode、
xattr bytesのhash、ACLの全entryとflagsをPythonでも照合した。結果は両方pass。
実filesystemへの極端な時刻/所有者の設定は行っていない。

compile 386入力、既存fixture 41入力、interop工具2入力を作業repoとcontainerコピーで照合した。
全候補入力が個別実行されたという意味ではない。2つの小さい生成tar/DEBとnativeログを保持する。
これらは通常file一つだけの試験成果物であり、設定済み全rootや配布イメージではない。

test-01は新testのsigned演算可視性不足によるcompile失敗。test-02は49/814 assertion成功だが、
相互読戻し前の版である。test-03はSCHILY encoded名を上流readerがliteral名として返すため、
長い名前が既存の255 byte上限で拒否された。失敗と途中成功を最終結果に読み替えない。
raw名/空値も一致したLIBARCHIVE形式を新規出力に選び、既存SCHILY入力の解釈は変えていない。

writer-probeの固定libarchive 3.7.4では、供給した負の小数時刻が異なるPAX値になり、指定birthtimeも
省略された。新codecは正しい十進数と明示birthtimeを出力する。reader-time-probeでは、正しいPAXを
直接upstream readerへ渡しても負の小数時刻がtimespecと一致しなかった。native payloadのframing補正は
今回確認したが、root_extract.cはまだupstream entry時刻を直接使うため、実適用側の修正が必要である。
これらは明記した人工入力/固定版の観測であり、他版や全ケースへの一般化ではない。
上流ソースはコピー/改変していない。

構造/台帳/link/lint/licenseと生成CIも成功。数学的入力と共有vendorは不変。
全suite/証明/旧カオス/VMは反復していない。まず実workerの時刻補正、次に元属性adapterと全rootの
stream/CAS保持・再確認を接続する必要がある。全属性/inode適用、全managed認可、特権observer、
世代保持/復旧・実root/boot、完全置換ISOと全翻訳等も未完である。
