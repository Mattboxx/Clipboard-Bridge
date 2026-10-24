# Clipboard Bridge 2.0.20

Open shared files directly from Windows History and scroll long clipboard previews
more comfortably. Existing settings, accounts, hotkeys and shared data are preserved.

## What Changed

- Select a file or image and choose **Open file** or **Open folder**, without first
  copying it. The same actions are in the right-click menu. For groups, choose a
  member in the filename list. Files download in the background only when needed
  and previously saved downloads are reused. Opening does not change your clipboard.
- Common executable/script and macro-enabled document types need an extra
  confirmation. This is not an antivirus check: only open files you trust.
- The full-text preview now reserves room for a visible vertical scrollbar, in
  both the side and bottom layouts. Middle-click, then move above/below the starting
  point to scroll; greater distance increases speed. Click again, press a key or
  move focus to another control to cancel. Holding the middle button and dragging also works;
  release ends that gesture. Ordinary wheel and scrollbar scrolling still work.
- Keep the lightweight Python/Tk application and its existing features. A Rust
  rewrite is not included; no new runtime dependency or security bypass is added.

## Downloads and Compatibility

Installer and portable EXE are provided for **x64** and native **ARM64**. Use
**Settings > Updates** in Windows 2.0.18 or later, or download your matching package.
Automatic installation remains optional. No manual deletion of user data is needed.

Standalone Docker server **1.0.10**, Android **1.0.0-beta.12**, store catalogs and
the two signed iPhone Shortcuts are unchanged. The unchanged APK and Shortcuts
are included for convenience. Source code remains in the repository.

Windows binaries remain **unsigned** and can require Windows approval or be
blocked. Do not disable protection. Use a trusted LAN/private VPN; optional URL
credentials are readable and HTTP is not encrypted.

Automated native GUI, clipboard, installer and update tests are not a physical
phone/NAS/VPN or Windows security-prompt acceptance test.
