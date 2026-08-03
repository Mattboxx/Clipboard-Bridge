# Changelog

All notable user-facing changes are documented here.

## 2.0.6 - 2026-08-03

### Fixed

- Preserved uncommon file extensions, including `.shortcut`, by using multipart file
  uploads from Windows and Android.
- Forced generic files to download with their original filename instead of being treated
  as unnamed binary data by browsers and mobile clients.
- Added an optional `filename` URL parameter for raw iPhone Shortcut uploads.

## Server 1.0.4 - 2026-08-03

- Added filename fallbacks for raw uploads from iPhone and generic HTTP clients.
- Returned individual files and grouped archives as named attachments.

## 2.0.5 - 2026-08-03

### Added

- Grouped multi-file clipboard items across the standalone server, Windows and Android.
- Automatic iPhone multi-file transport through `/clipboard/bundle` and lightweight
  type detection through `/clipboard/latest/meta`.
- Android multi-selection from the file picker, Share Sheet and clipboard.

### Changed

- Multiple files selected in one operation now occupy one server-history row and are
  restored together on Windows and Android.
- Generic HTTP clients and iPhone Shortcuts receive grouped files as a ZIP transport.
- Updated the English and Italian documentation and the public website.

### Security

- Added archive member, expanded-size, path and encryption validation for iPhone ZIP
  transport uploads.

## Server 1.0.3 - 2026-08-03

- Added grouped multipart uploads and safe iPhone ZIP transport handling.
- Added metadata-only lookup and per-member raw download endpoints.
- Preserved arrival order across text, images, individual files and file groups.

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
