# Changelog

All notable user-facing changes are documented here.

## 2.0.4 - 2026-07-30

### Changed

- Centralized Windows release versioning and added package consistency checks.
- Displayed the installed client version in Settings.
- Updated the onboarding, download pages and release documentation.
- Hardened GitHub Actions by pinning current actions to reviewed commit hashes.

### Fixed

- Aligned the documented Docker server and application-store package with server
  version 1.0.2.

## 2.0.3 - 2026-07-30

### Added

- Separate notification controls for received text, images and files.
- Automatic incoming file downloads with clickable Windows notifications.
- Connection status in the tray and detailed checks in Settings.
- Single-instance protection to prevent duplicate tray icons.

### Fixed

- Preserved client configuration when upgrading from earlier Program Files
  installations.
- Copied received files to the Windows clipboard.
- Improved iPhone upload compatibility for Unicode text and arbitrary files.

## 2.0.2 - 2026-07-29

- Added per-user installation and portable Windows packages.
- Moved runtime data to the current user's writable application-data folder.

## Server 1.0.2 - 2026-07-30

- Added robust text and file parsing for iPhone Shortcuts.
- Added optional isolated accounts from an environment variable or accounts
  file.
- Added upload-size controls and security response headers.
