# Clipboard Bridge 2.0.18

A clearer Windows interface and optional GitHub updates. Existing connections,
credentials, history and hotkeys are preserved. Older clients need one manual
upgrade to obtain the new update controls.

## Choose Your Download

- **Intel/AMD Windows PCs:** x64 installer or portable EXE.
- **Windows 11 ARM/Snapdragon:** native ARM64 installer or portable EXE.
- The installer uses your Windows user account; portable replaces no installed app.
- Android remains **1.0.0-beta.12**, standalone Docker server **1.0.9**.
- Both signed iPhone Shortcuts are unchanged and included for convenience.

## Clearer Desktop

- Compact History with grouped Send/Receive actions, search and inline type filters.
- Automatically follow the selected connection: Windows Server mode uses its own
  history; Client mode uses the configured host. No competing Local selector.
- Lightweight matte light/graphite styling inspired by Plexo's UI components.
  Separate icon columns, consistent dark hover states and slim loading indicators.
- Responsive image and PDF inspector. No Electron/Qt runtime or real desktop blur.
- Matching website and actual desktop captures using public example content only.

## Optional Updates

Open **Settings > Updates** to check, download or install. Checks default on;
automatic installation is **off until you enable it and Save**. A manual check
never installs by itself. Automatic restart waits for Settings and active transfers.

The updater selects stable Windows releases independently of Android/server tags,
keeps your architecture and installed/portable format, and checks official URLs,
SHA-256, size, PE architecture and embedded version. Cancel remains available
through preparation, until the UI commits the restart. A separate helper waits
for graceful exit, preserves user data and attempts recovery if installation fails.
Retries use fresh handoffs; abandoned downloads expire after seven days.

## Important Limits

**Windows executables remain unsigned.** SmartScreen or Smart App Control may
require approval or block them. No protection is disabled or bypassed. Hash checks
verify integrity, not an independent publisher identity. Automatic updates cannot
promise an unattended installation under every Windows security policy.

Source checkouts and read-only portable folders require manual updates. Recovery
cannot undo every external installer or Windows failure; use the official installer
if recovery fails. The bounded release scan fails clearly if it cannot finish.

Use a trusted LAN or private VPN. Optional account/token URL values are readable;
HTTP is not encrypted. Apple actions are user-triggered and Android remains a beta
subject to background restrictions. Authentication and signed Apple exports have
not changed in this release.

Native build and upgrade CI is not a physical phone, NAS, VPN or Windows security
prompt test. Remaining checks are listed in the
[manual acceptance plan](https://github.com/Mattboxx/Clipboard-Bridge/blob/main/maintainer/MANUAL_TESTS.md).
Developer sources remain in the repository, not among the download attachments.
