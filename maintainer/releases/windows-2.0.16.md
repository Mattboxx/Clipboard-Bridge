# Clipboard Bridge 2.0.16

A Windows maintenance release focused on reliable clipboard receipt and preserving
your history. Your saved settings, account details, hotkeys and history stay in
your existing user folder. Quit Clipboard Bridge before updating or changing
between x64 and ARM64.

## Choose Your Download

- **Most Windows PCs:** use the x64 installer. The x64 portable EXE needs no installation.
- **Windows 11 on ARM/Snapdragon:** use the native ARM64 installer or portable EXE.
- The Android APK is the **unchanged public beta.11**, not a new stable Android release.
- The two signed **iPhone Shortcuts are unchanged** and remain included for convenience.
- The stable standalone Docker server remains **1.0.8**. Windows Server mode is included.

## What Changed

- A busy or failed Windows image/file clipboard write now reports failure instead
  of claiming the item was received. Brief clipboard contention is retried.
- File groups are checked as a complete selection. If a member is already missing,
  the app reports it instead of replacing the clipboard with only the remaining files.
- Damaged local or Windows-host history is preserved, with a clearer error. A broken
  optional local cache no longer prevents healthy remote transfers.
- Native x64/ARM64 build checks cover clipboard round trips, portable and installed
  payloads, and saved-configuration preservation on disposable runners.
- Updated Windows dependency floors and improved packaging checks.
- Clearer README/site illustrations: cursor-free Windows History and the actual
  optional Docker web interface, all using public sample data.

## Important Limits

**Windows binaries are unsigned.** SmartScreen or Smart App Control may block them.
Do not disable Windows protection. SHA-256 values verify file integrity, not a
trusted publisher signature. See [code-signing status](https://github.com/Mattboxx/Clipboard-Bridge/blob/main/CODE_SIGNING.md).

Use a trusted LAN or private VPN. Accounts and tokens remain optional; URL
credentials are readable and plain HTTP does not encrypt them. Apple actions are
user-triggered, and Android background clipboard restrictions still apply.

Automated checks do not establish every physical phone, standard-user desktop,
sleep/resume, VPN or application-paste scenario. These remain in the
[manual acceptance plan](https://github.com/Mattboxx/Clipboard-Bridge/blob/main/maintainer/MANUAL_TESTS.md).
CF_HDROP references files by path: a later deletion after validation is still possible.

The automatic GitHub source archives contain developer files. Ordinary users need
only an installer, portable EXE, APK or iPhone Shortcut from the assets below.
