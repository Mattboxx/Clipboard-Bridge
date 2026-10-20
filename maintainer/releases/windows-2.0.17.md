# Clipboard Bridge 2.0.17

A Windows maintenance release that keeps transfers tied to the server and account
where they started. Existing settings, history and hotkeys are preserved. Quit
Clipboard Bridge before updating or switching between x64 and ARM64.

## Choose Your Download

- **Most Windows PCs:** choose the x64 installer or the portable EXE.
- **Windows 11 on ARM/Snapdragon:** choose the native ARM64 installer or portable EXE.
- The Android APK remains the **unchanged public beta.11**.
- Both signed **iPhone Shortcuts are unchanged** and included for convenience.
- The stable standalone Docker server remains **1.0.8**; Windows Server mode is included.

## What Changed

- Late replies from a previous account or server no longer replace the clipboard,
  update the current history cursor, or announce an obsolete receipt. Switching
  away and back is detected too, including changes to passwords and API tokens.
- Changing connections does not automatically re-share the previous clipboard
  into the newly selected account. A fresh copy can still be synchronized.
- File groups and queued History actions retain their original connection.
  Network downloads do not hold the Settings update lock.
- Testing unsaved credentials updates only that Settings window, not the saved
  connection's tray status. Edited or closed forms discard late test replies.
- Invalid history replies are no longer reported as a successful connection.
- Failed hotkey registration leaves the saved connection unchanged.

## Important Limits

An upload already accepted by the original server cannot be recalled. Files already
downloaded may remain in Downloads or the original connection's cache; this update
prevents obsolete clipboard application, not transactional filesystem rollback.

**Windows executables are unsigned.** SmartScreen or Smart App Control may block
them. Do not disable Windows protection. Checksums verify integrity, not publisher
identity. See the [signing status](https://github.com/Mattboxx/Clipboard-Bridge/blob/main/CODE_SIGNING.md).

Use a trusted LAN or private VPN. Accounts and tokens remain optional and URL
credentials are readable; HTTP does not encrypt them. Apple actions are
user-triggered and Android background restrictions still apply.

Automated checks do not validate every physical phone, sleep/resume, standard-user
upgrade or VPN scenario. See the [manual acceptance plan](https://github.com/Mattboxx/Clipboard-Bridge/blob/main/maintainer/MANUAL_TESTS.md).
Developer source is available in the repository; ordinary users only need the
installer, portable EXE, APK or iPhone Shortcuts below.
