# 設定の属性採用元とpermission継承

対象subject: `097b5508227fd5dc012cc68d526bee88fe2873a38184bb1e1c47c7653e3bfba8`。本番認定ではない。

元DEB/実snapshotからの選択へ、対象と退避の完全属性参照・元path・数値permissionと継承元を追加した。
NIACCH02へ束縛し、Read_Effectsは同じStore予約の全参照とlive namespaceを再確認する。
既存localがあればvendor内容とvendor退避もlocalの全permission bit/UID/GIDを継承する。
初回導入は元payloadの数値を使う。localの保持/退避は完全NIACOBS1を参照する。

固定Debian 13 image、通常UID 1000、networkなし、3 GiB/swap0/CPU1/pids128で対象mainを
`gprbuild -f -j1`により再compileした。最終test-02.logは270 assertion成功。
実mode 0600/06740、local owner、vendor fixtureの0640/1001/1002、双方の退避、
欠落/初回導入、永続参照の完全一致、mode変更/退避先作成/別閉包による全出力消去を確認した。
実際のrootへのchownや抽出は行っていない。

test-01.logは新testのfixture値の誤認で失敗した。data.tarを抽出せず読み、実値を確認して
期待値だけを修正した。途中失敗を成功に読み替えない。fixture-permissions.jsonに原本hashと実値を記録した。
compile-inputs.jsonは最終の380候補入力のhashであり、そのすべてを実行したという主張ではない。
fixture 22入力とともに作業repoとcontainerコピーを照合した。commands.jsonに実コマンドを保持する。

構造/台帳/link/lint/licenseと生成CIを検査した。数学的入力と共有vendorは不変。
全suite/証明/旧カオス/VMは反復していない。上流permission規則の参照元hashは
[前工程の原本調査](../conffile-observation-01/upstream-source.json)を参照。
上流ソースのコピーや改変は行っていない。

全属性は元recordの参照として保持している。ACL/capability/chown/chmodやflags/時刻の実適用、
全namespace/link計画とroot archiveへの接続、特権observer、全managed認可、実root/boot/復旧、
完全置換ISOと全翻訳等は未完。live sessionからの読出しを独立durable readerや認証UIにしない。
