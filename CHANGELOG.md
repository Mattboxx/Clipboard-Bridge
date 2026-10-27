# Changelog

All notable user-facing changes are documented here.

## Unreleased

No pending release changes.

## Server 1.0.11 - 2026-10-27

- Move optional Ko-fi support above the clipboard controls, alongside a direct
  GitHub repository link. Keep the support label and explanatory tooltip localized
  in all seven existing languages, with keyboard focus and narrow-screen wrapping.
- Keep API URLs, optional authentication, sessions, storage paths and image
  architectures unchanged. Windows 2.0.20, Android beta.12 and Apple exports are unchanged.
- Add researched CasaOS submission files: Big Bear universal source and generated
  Compose, a HomeAutomation scope candidate, and a LinuxServer eligibility inquiry
  with a separate numeric-user deployment example. These do not imply acceptance.

## Windows 2.0.20 - 2026-10-24

- Add Open file and Open folder to selected images/files in History and its context
  menu, including a member selector for groups. Download on demand in a background
  task, reuse saved files and leave the clipboard unchanged. Discard obsolete open
  requests after selection/account changes or window closure; confirm common
  executable/script and macro-enabled document types before opening.
- Reserve space for the text preview's vertical scrollbar in narrow and wide
  windows. Support middle-click autoscroll with direction/speed controlled by pointer
  distance, middle-drag scrolling, and cancellation on another click, keyboard input,
  focus loss, hiding or closing the preview. Keep full Unicode text read-only.
- Keep the lightweight Python/Tk interface, existing settings, automatic sync,
  updater and host mode. No Rust rewrite or new runtime dependency is introduced.
  Server 1.0.10, Android beta.12, store image tags and signed Apple exports are unchanged.

## Server 1.0.10 - 2026-10-24

- Localize the web interface, login, confirmations and device setup in English,
  Italian, Spanish, French, German, Portuguese and simplified Chinese. Remember
  the browser's language choice while keeping English as the default.
- Add an expandable connection guide for Windows, Android and Apple Shortcuts,
  persistent Docker storage and safe updates. Link the public website and full
  tutorial beside optional Ko-fi support without leaking account URLs externally.
- Keep existing accounts, sessions, ports, data paths and Apple API URLs compatible.
  Include translations inside the amd64/arm64 Docker image, with no new dependency.
- Refresh catalog metadata and installation instructions for ZimaOS v2 Productivity.
  Windows 2.0.19, Android beta.12 and signed Apple exports remain unchanged.

## Windows 2.0.19 - 2026-10-24

- Load the complete selected text in History Preview instead of the
  140-character history extract or a 4,000-character cutoff. Keep it read-only and
  scrollable, fetch it in the background and insert large text incrementally.
  Discard stale replies after selection, visibility, connection or window changes.
- Preserve Unicode, emoji, whitespace and empty text. Keep image/PDF previews,
  clipboard contents and existing settings unchanged. Standalone server 1.0.9,
  Android beta.12, store catalogs and signed Apple exports are unchanged.

## Windows 2.0.18 - 2026-10-23

- Recompose History around a full-width compact list, a single transfer band and
  inline type filters. Follow the configured host automatically instead of showing
  competing Local/Server source selectors. Preserve existing cached data.
- Add lightweight flat light/graphite surfaces, restrained blue accents, consistent
  native glyph spacing, slim loading indicators and a responsive image/PDF inspector.
  Give history icons their own bounded column and refresh their colors on theme changes.
- Override light hover/readonly defaults in dark selectors. Cache symbol fonts,
  avoid resetting an unchanged Tk theme and redraw update status only when it changes.
- Refresh the public site with matching surfaces, reduced-motion-aware transitions
  and actual desktop captures using public sample data only.
- Add Settings > Updates in English and Italian: manual checks, download progress,
  cancellation and optional automatic download/installation from official GitHub
  stable releases. Automatic checks are enabled; installation is opt-in.
- Select native x64/ARM64 and installed/portable assets, reject downgrades,
  prereleases, unexpected URLs, missing hashes and damaged downloads. Verify the
  GitHub SHA-256, embedded version and executable architecture before replacement.
- Run replacement outside the UI process, wait for the app to exit, preserve user
  data and restart. Attempt to restore the old EXE on installation/start failure.
  Defer automatic restart while Settings are open and avoid failed-update loops.
- Preserve Windows Internet-zone checks. Packages remain unsigned and may require
  Windows approval; the updater does not disable or bypass security protections.
- Exercise actual frozen portable/installer upgrades on disposable native runners.
- Find the newest stable Windows version even when Android or server releases were
  published later. Fail clearly if the bounded release scan cannot finish.
- Keep cancellation effective during preparation and helper startup; require an
  explicit UI handoff before replacement. Wait for graceful host shutdown without
  an arbitrary two-minute timeout and report failures before restarting recovery.
- Use a fresh handoff for retries and clean up abandoned pre-handoff downloads after
  seven days without touching unfinished helpers or unrelated files.
- Android beta.12, standalone server 1.0.9, store catalogs and signed Apple exports
  are unchanged. Older Windows versions need one manual upgrade to get the updater.

## Server 1.0.9 / Android 1.0.0-beta.12 - 2026-10-21

- Raise the standalone server's supported Flask minimum to the reviewed patched
  release. Publish the stable amd64/arm64 image before updating store catalogs.
- Bind Android operations and every member of a file group to their initial server
  and account. Discard obsolete results after a connection change instead of mixing
  sources or advancing the new account's receive cursor.
- Ignore late Android history/operation results after pause, refresh or account
  changes; retain the source of history selections and delete confirmations.
- Test draft Android connection settings without saving them. Keep unrelated
  automation/notification changes from resetting the connection or receive cursor.
- Reject an empty username in Android Account mode instead of silently requesting
  the general clipboard. Shared space without credentials remains supported.
- Stage Android file groups before publishing them to Downloads. If writing,
  publishing or applying the clipboard fails, attempt cleanup of every newly
  created download and remove this operation's cached files. Preserve existing files.
- Treat a failed MediaStore publication as an error rather than claiming receipt;
  log a content-free warning if rollback cannot remove an owned file.
- Preserve Android downloads marked as files even when their MIME type is `text/*`.
  Ordinary clipboard text remains plain Unicode; actual documents keep their bytes.
- Remove files created by an interrupted Android cache download, including completed
  members of a failed group, without touching unrelated cached files.
- Reject missing upload acknowledgements and non-history responses instead of showing
  false Android send/connection success.
- Refuse account access when distinct configured names resolve to the same physical
  directory on a case-insensitive or filename-normalizing filesystem. Keep the
  general clipboard and unrelated accounts available; do not relocate existing data.
- Preserve existing history when its index is malformed or unreadable instead of
  treating it as empty, in the standalone host, Windows host and local history.
- Return a safe `503 history_unavailable` response rather than overwriting damaged
  history; unaffected standalone accounts remain available.
- Flush a complete temporary index before atomic replacement and remove temporary
  files after failed commits. Keep previous indexed files on failed uploads.

## Windows 2.0.17 - 2026-10-21

- Discard obsolete receive results and notifications after a server, account,
  password or token change, including switching away and back.
- Avoid automatically re-sharing the previous connection's clipboard into a new
  account. Keep queued file sends, history actions and file-group downloads bound
  to their original connection without holding Settings locks during HTTP.
- Recognize a fresh copy after switching connections even when its contents match
  the previous clipboard; do not mistake a remote receipt for a new user copy.
- Keep draft connection checks inside Settings without changing active tray status;
  discard replies after editing/closing and reject malformed history responses.
- Do not publish changed connection settings before hotkeys validate successfully.
- Update Windows x64/ARM64 installer, portable and website download references.
- Android beta.11, signed Apple exports and stable Docker server 1.0.8 are unchanged.

## Windows 2.0.16 - 2026-10-20

- Check native image/file clipboard failures before claiming receipt. Prepare
  memory before clearing the clipboard, use an invisible owner, retry brief
  contention and release only buffers still owned by the application.
- Reject incomplete file selections rather than silently copying fewer files
  and marking the whole group as received. Keep the previous clipboard intact
  when a file is already unavailable at the preflight check.
- Preserve damaged local/Windows-host history instead of treating it as empty;
  warn clearly and keep healthy remote sharing working when the local cache fails.
- Build with reviewed Requests and Pillow security floors and a pinned PyInstaller.
- Preserve extra release-folder assets; preflight files and read optional APK
  metadata instead of hard-coding its version during packaging.
- Verify native x64 and ARM64 executables and installers, configuration preservation
  and actual clipboard round trips on disposable CI runners.
- Refresh the Windows screenshot without a mouse pointer; add real Docker web
  interface screenshots to the bilingual README and responsive website.
- Keep the existing signed Apple exports and Android beta.11 download available
  unchanged. No new stable server image or Android release is included.
- Windows packages remain unsigned. Physical device acceptance is not implied
  by automated tests; see the release notes and manual test plan.

## 2.0.15 / Server 1.0.8 / Android 1.0.0-beta.11 - 2026-10-14

- Deliver copied RTF as plain Unicode text in both server modes; preserve emoji and visible hyperlink labels.
- Prefer Windows Unicode clipboard content, falling back to RTF when no plain-text format exists.
- Keep actual RTF documents and file groups byte-for-byte unchanged.
- Prevent a sync echo when restoring rich text from an older server.
- Preserve existing account/token URLs on every client, without additional Apple Shortcut steps.
- Fix Android's rejection of non-ASCII password/token HTTP headers.
- Redact credential query values from Windows crash logs and Android communication errors.
- Make the remembered web session duration configurable without changing the existing default.
- Keep authentication and HTTPS optional for trusted LAN/VPN use.
- Include the History hotkey toggle from 2.0.14.
- Signing work is deferred; Windows packages remain unsigned.

## 2.0.14 - 2026-10-14

- The History hotkey now toggles the window: open, close, then reopen.
- Tray clicks continue to open or focus History without toggling it closed.
- Close through the normal cleanup handler, cancelling searches, previews and polling.
- Cancel the initial refresh too, including a rapid open/close before it has run.
- Keep Settings and the background application running when History closes.
- Preserve hotkey configuration, credentials and clipboard history.
- Windows x64 and native ARM64 packages; standalone server, Android and iPhone downloads are unchanged.

## 2.0.13 - 2026-10-14

- Fix History shortcuts lost by the previous key-release listener.
- Register global shortcuts with Win32 RegisterHotKey and a dedicated message loop, independent of Tk focus and key-release timing.
- Use MOD_NOREPEAT to avoid repeated actions when keys are held down.
- Set any shortcut by clicking Set keys and pressing a combination; Escape cancels recording.
- Pause shortcuts during recording so assigning Send cannot upload the clipboard accidentally.
- Detect system/other-app conflicts and restore the old bindings without saving invalid settings.
- Preserve credentials, custom key combinations, notification settings and history on upgrade.
- Windows x64 and native ARM64 installer/portable packages; source files stay in the developer repository, not release attachments.
- Standalone server remains 1.0.7; Android and iPhone downloads are unchanged.

## 2.0.12 - 2026-10-14

- Configurable global shortcut to open or focus Windows History, initially Ctrl+Alt+H.
- Change Send, Receive and History shortcuts in Settings without rebuilding the app.
- Open History on the GUI thread, without uploading the clipboard or creating another window.
- Reject invalid or duplicate shortcuts before saving; preserve existing credentials and custom bindings.
- Keep working Send/Receive bindings if an older configuration conflicts with the new default.
- Do not let the automatic connection check clear Settings validation errors.
- Clearer English and Italian READMEs: beginner setup first, expandable device instructions and complete developer/API reference.
- Optional Ko-fi support link and explanation at the end of both READMEs.
- Windows x64 and native ARM64 installer/portable packages; standalone server remains 1.0.7, Android and iPhone downloads are unchanged.

## 2.0.11 - 2026-10-14

- Real image thumbnails in the optional Windows History preview pane, for server and local items.
- PDF first-page thumbnails and page counts, with a bundled PDFium renderer.
- Preview the first image or PDF in a file group without downloading its other members.
- Preserve aspect ratio, transparency and camera orientation; keep a stable preview area.
- Load thumbnails off the UI thread, discard stale selections and retain account isolation.
- Limit thumbnail memory and download size; report unavailable images without affecting transfers.
- Clearer project website with consistent typography, device-based downloads and current screenshots.
- The top Support me button opens Ko-fi directly instead of scrolling down the page.
- Documented manual Mac integration through Apple Shortcuts, without claiming a native Mac client.
- Native Windows 11 ARM64 portable and installer packages, built and tested on an ARM64 runner.
- Verify every bundled native library, frozen application startup, local server and single-instance behavior before exporting ARM64 builds.
- Both Windows architectures retain the same application identity and per-user configuration.
- Standalone server remains 1.0.7; Android and iPhone downloads are unchanged.

## 2.0.10 - 2026-10-13

- Compact unified Windows history with at least 17 visible rows at its initial size.
- Flat Server / This PC selector and sidebar Settings navigation instead of notebook tabs.
- Thin draggable scrollbars without arrow buttons; native Windows checkbox indicators.
- Explicit icon-and-text Refresh and Previous/Next buttons with higher contrast.
- Optional preview pane; double-click or Enter to copy the selected item.
- Copy local text, images and file groups directly, without having to send them first.
- Dark appearance by default, with live Light/Dark preview and a saved preference.
- Restore the saved appearance when cancelling Settings; keep open windows consistent.
- Reopen existing History/Settings windows rather than creating duplicates.
- Optional Ko-fi support link at the bottom of Windows Settings and the server web page, without popups.
- Friendly support explanation and thank-you in the selected English/Italian language.
- Visible Support navigation and donation section on the project website, including mobile.

## Server 1.0.7 - 2026-10-13

- Added a discreet Ko-fi support link in the web footer; no API, account or storage changes.

## 2.0.9 - 2026-10-13

### Added

- Search history previews and filenames, including every member of a file group.
- Filter history by text, image, file or file group in the Windows client and web page.
- Paginate server history in both interfaces instead of hiding older entries.
- Extend the history API with `q`, `offset`, `total` and `has_more` in both server modes.
- Modern Windows Settings with scrollable tabs, consistent typography and clear controls.
- A structured Windows history table, selected-item preview and quick send/receive actions.
- Left-clicking the Windows tray icon opens History; sending remains an explicit menu action or hotkey.

### Fixed

- Do not silently upload only part of a group when a selected file is missing.
- Re-send text copied again after the Windows clipboard has been cleared.
- Reject malformed, duplicate or incomplete HTTP request lengths in Windows Server mode.
- Reject negative file-group member indexes and report missing deleted items consistently.
- Snapshot embedded-server reads before concurrent history trimming or deletion.
- Keep existing history files when an index write fails; remove incomplete new uploads.
- Recover safely from invalid saved Windows settings without erasing valid credentials.
- Report failed web deletions instead of reloading as though they succeeded.
- Ignore outdated history-search responses and cancel callbacks when the window closes.
- Keep the server/account fixed for an entire in-flight upload, receive or file group,
  even when Settings change; do not assign its response/cache to another account.
- Remove incomplete received files after a disk-write failure.
- Prevent older connection checks from overwriting a newer successful check.

## Server 1.0.6 - 2026-10-13

- Added history search, type filters and pagination to the API and optional web page.
- Preserved existing data when index commits fail and removed partial upload files.
- Made web deletions report errors instead of appearing to succeed.
- Kept existing iPhone and Android endpoints and optional authentication compatible.

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
