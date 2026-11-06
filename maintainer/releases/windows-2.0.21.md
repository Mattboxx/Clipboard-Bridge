# Clipboard Bridge Windows 2.0.21

## Changes

- Enter one complete server address in Connection settings, for example
  `http://192.0.2.20:5088`. Existing IP/port settings are migrated without deleting
  account credentials, history, hotkeys or automation preferences.
- Connect device shows a copyable address and a locally generated QR for public
  downloads. The QR contains no account/password and does not pair devices.
- Preserve Client/Server modes, automatic synchronization, file groups, previews
  and the existing GitHub updater.

## Downloads

Installer and portable packages are provided for Windows x64 and native ARM64.
Use Settings > Updates in Windows 2.0.18 or newer, or download a matching package.
The existing Android beta.12 APK and two signed Apple Shortcuts are included,
unchanged, for convenience. Developer sources remain in the repository.

The standalone Docker server is updated separately to 1.0.12 with a simpler,
theme-aware browser interface and clearer device setup instructions.

## Compatibility and Validation

Windows packages remain unsigned and may require approval or be blocked by
Windows. Do not disable protection. Use a trusted LAN/private VPN; HTTP and
optional credential URLs are not encrypted. No AES mode or extra iOS app is added.

Native x64/ARM64 tests, installer data preservation, frozen update checks and
build provenance are verified by the linked release PR workflows. These are not
physical phone/NAS or Windows security-prompt acceptance tests. See the delivery
PR for exact build runs and SHA-256 evidence.
