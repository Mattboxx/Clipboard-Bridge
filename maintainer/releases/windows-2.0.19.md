# Clipboard Bridge 2.0.19

Read the complete text in Windows History Preview, not just a short extract.
Existing settings, connections, hotkeys and clipboard data are preserved.

## What Changed

- Enable **Preview** in History and select a text item to read its entire content.
  Scroll to the final line, including text longer than 4,000 characters.
- Fetch full text only when Preview is enabled. Keep network loading off the UI
  thread and insert large texts incrementally so the window remains responsive.
- Preserve Unicode, emoji, spaces, line breaks and empty text. Preview is read-only
  and never copies to the clipboard automatically.
- Discard obsolete replies when selection, account, host or preview visibility
  changes, or the window closes. Failed reads show an unavailable message instead
  of presenting an incomplete extract as the full text.
- Image and PDF previews are unchanged.

## Downloads and Updates

Choose x64 for Intel/AMD PCs or ARM64 for Windows on ARM. Both installer and
portable EXE are available. From 2.0.18, use **Settings > Updates**; automatic
installation is optional and off by default. Older versions need a manual upgrade.

Android remains **1.0.0-beta.12**, standalone Docker server **1.0.9** and custom
store catalogs remain on that server release. Their code did not change. The
unchanged APK and both signed iPhone Shortcuts are included for convenience.

**Windows executables remain unsigned.** Windows may require approval or block
installation; no security protection is bypassed. Use a trusted LAN or private
VPN. Optional account/token URL values remain readable and HTTP is not encrypted.

Automated native build, UI and upgrade checks are not physical phone, NAS, VPN or
Windows security-prompt acceptance tests. Remaining manual checks are recorded in
[MANUAL_TESTS.md](https://github.com/Mattboxx/Clipboard-Bridge/blob/main/maintainer/MANUAL_TESTS.md).
