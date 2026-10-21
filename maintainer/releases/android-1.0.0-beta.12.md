# Clipboard Bridge Android 1.0.0-beta.12

Public Android beta maintenance update, signed with the existing release key and
versionCode 12. Install it over the previous APK without uninstalling: app data and
settings stay in the existing application profile.

## Changes

- Pin operations and every file-group member to the server/account where they started.
  Discard obsolete results after connection changes, pause, refresh and delete dialogs.
- Test unsaved connection settings without changing the active connection. Unrelated
  notification/automation preferences no longer reset the receive cursor.
- Reject an empty username in Account mode instead of silently using shared space.
  Accounts/tokens remain optional; the general clipboard is still supported.
- Stage file groups before publishing to Downloads. On write/publication/clipboard
  failure, attempt cleanup of this operation's newly created files and cached members.
  Preserve unrelated files and report a content-free warning if rollback fails.
- Keep real `text/*` documents as files and reject missing upload acknowledgements
  or malformed history responses instead of reporting false success.

## Compatibility And Limits

Requires Android 10 or later. Compatible with server 1.0.9 and Windows host 2.0.17;
existing Apple URL/optional credential formats are unchanged.

Android still restricts background clipboard access. Battery policy, sleep/resume,
Share Sheet/Quick Settings and cross-app file pasting require physical device checks;
unit tests and a signed release build do not establish those results. Do not uninstall
the previous app to update. Use trusted LAN/private VPN rather than public exposure.
