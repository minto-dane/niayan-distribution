# 供給記録observerのcredential署名provider

`archive_credential.issue_from_credential`は、既存のTUF/OpenPGP原本認証を実行してから、
保護されたFDで受け取った32-byte Ed25519 seedを読む。任意message、既成の観測JSON、
呼出側が組み立てた認証結果を署名する入口はない。既存NIASUP01の形式とnative検証は維持する。
これは内部APIであり、公開管理コマンドや通常起動で有効になるサービスではない。

## 入力と保護

supervisorが要求とは独立したsite設定から、公開鍵pin、供給scope、epoch下限、最大lifetimeを
渡す。scopeは正確なTUF cache identityとtargetから再計算して一致を要求する。
署名closureも固定domain、scope、epochと期限を検査し、一回の発行処理につき一度だけ使う。
元の発行器が署名を独立公開鍵で検証し、保持TUF policyと時刻を最後に再検査する。
成功は供給原本の認証であり、同意・世代公開・DEB効果・起動の許可ではない。

credentialは読み取り専用の通常file FDで、正確な32 bytesを要求する。
次のOS配備形態だけを受け付ける。

- 読み取り専用mount上の単一link。service UID所有0400、またはroot:root所有0440で、
  rootと正確なservice UIDだけにreadを与えるsystemd形式のPOSIX ACL。
  後者の表示上のgroup read bitはACL maskであり、group所有者や他userへの許可ではない。
- service UID所有0400、link数0で、WRITE/GROW/SHRINK/SEALをすべてsealしたmemfd。
  supervisorはseal後に読み取り専用FDとして渡す。

単にO_RDONLYで開いた通常の書込可能filesystem上の鍵fileは拒否する。
FD属性・ACLを読取と署名の前後で再検査し、導出した公開鍵も独立pinへ照合する。
読み取り専用mountの表示だけで配備元の真正性や別の書込可能aliasの不在を証明しない。
その由来、mount namespace、独立設定の保護は信頼するsupervisorの責務である。

借用FDはCLOEXEC付きで複製し、全終了経路で複製を閉じる。preadで呼出元offsetを動かさない。
鍵を読む前にcore limitをsoft/hardとも0とし、Linuxのdumpableを0へ固定する。
このprocess全体への変更は戻さないため、専用の短命な非root observerで使用する。
鍵の内容をargv・環境変数・診断へ入れず、systemdの環境変数にはcredential directoryのpathだけが入る。
Python/OpenSSLの全copyのzeroizationやhardware保護は主張しない。process終了、別専用UID、
MemorySwapMax=0、有限のservice期限、保護されたコードとimport pathが配備条件である。

## systemdへの接続と検証境界

`worker/check_archive_credential.py`は使い捨てQEMU/systemd VM専用の受入工具である。
root managerのLoadCredentialで一時seedを専用UIDへ渡し、実TUF/OpenPGP認証、credential署名、
native CAS原本検査まで接続する。systemd 257で実際に渡されるroot所有・ACL付き0440と
read-only mountを確認する。serviceはcapabilityなし、NoNewPrivileges、ProtectSystem=strict、
PrivateTmp、PrivateDevices、swapなし・512 MiB・CPU1相当・32 tasks・90秒に制限する。
DEB fixtureはprivate親directory内でcontrol directoryの0755を明示し、service umask0077を維持する。

正常時の五つのnative bridge判定と、別公開鍵・短いcredential・credential欠損の拒否を検査する。
非root単体試験はsealed memfd、FD保持と失敗時close、scope/key/floor/lifetime、
原本認証失敗時の鍵の非読取、mutable/非private/欠損/別種FDとUID0拒否を扱う。
既存receipt試験の保持policy変更・期限・時計逆行の検査も維持する。

VMのTUF transportは実署名付きのprocess内fixtureであり、HTTPS配備の受入とは数えない。
鍵はテスト用にVM内で生成して終了時にsource fileを削除し、秘密鍵を証跡へ出力しない。
この工具のfixtureや一時unitを本番サービスとして配布しない。
配布可能なobserver、内部client、明示provisioningと実HTTPSの接続は
[archive-observer.ja.md](archive-observer.ja.md)を参照。
本番siteの設定導入、鍵の生成/更新/失効、site floor更新と完全なpublisher/controller接続は
配布serviceでも別の残作業である。
