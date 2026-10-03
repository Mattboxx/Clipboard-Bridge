# Changelog

All notable user-facing changes are documented here.

## 2.0.8 - 2026-10-03

### Fixed

- Retried failed automatic uploads instead of silently forgetting local content.
- Retried a temporarily busy Windows clipboard without repeated downloads or notifications.
- Kept newer text/images on the clipboard when older files arrive in the same polling cycle.
- Prevented manually received history items from being uploaded back to the server.
- Preserved empty files, long Unicode filenames and unsupported image formats as files.
- Cleaned up interrupted multi-file downloads and reused completed downloads.
- Detected content changes in files copied from the same path.
- Reported server errors when deleting history entries instead of appearing to succeed.

### Performance

- Polled metadata instead of downloading unchanged Base64 file/image content.
- Downloaded individual files through their raw endpoint.
- Skipped repeated bitmap reads and hashing when the Windows clipboard has not changed.

## Server 1.0.5 - 2026-10-03

- Preserved exact CRLF, CR and LF line endings in both server modes.
- Added UTF-32 BOM detection alongside UTF-8 and UTF-16.
- Supported Unicode account passwords and tokens without authentication errors.
- Preserved literal percent sequences in URL filenames.
- Rejected malformed JSON without replacing the latest clipboard item.
- Made the Windows embedded-server index writes atomic.
- Added regression coverage for concurrent uploads and large file groups.

## 2.0.7 - 2026-08-10

### Fixed

- Prevented Windows from reporting a locally uploaded clipboard item as newly received.
- Prevented manual uploads from being immediately uploaded a second time by auto-sync.
- Remembered the last handled server item across restarts to avoid repeated notifications.
- Kept only the newest remote file group on the Windows clipboard when several items
  arrive between polling cycles.
- Made local-history writes atomic and removed consecutive duplicate text, image, file
  and grouped-file entries.

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
