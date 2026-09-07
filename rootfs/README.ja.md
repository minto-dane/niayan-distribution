# Nia 派生rootfs入力

os-releaseとread-only observer unit。ここにnode鍵・信頼値・要求台帳を置かない。owner UID/GIDはrootを意図するが本入力ではinstallしていない。通常fileは0644、unitは自動起動しない。

observerのExecStartはfirst-party artifact manifestの`usr/libexec/nia/hostctl`に一致させる。DynamicUser/PrivateDevicesによって読めない観測はunknownのまま。root又はMACを緩めて無理にhealthy=trueを出さない。kernel/build/実行時の隔離が有効かは別の受入試験を要する。

`/etc/os-release`を`../usr/lib/os-release`へ結ぶ操作はimage assemblerの認可された効果。ここではsymlinkを書き込まない。元Debianの同ファイルへの変更はNia派生成果物として来歴管理する。
