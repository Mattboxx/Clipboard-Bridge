# Architecture And Repository Layout

Clipboard Bridge is a small multi-client repository. A single selected host holds
the shared clipboard; clients send and retrieve its latest item and history.
The standalone server and Windows Server mode are alternatives, not two required
steps in a transfer.

## Runtime Components

| Component | Entry point | Responsibility |
| --- | --- | --- |
| Standalone host | `clipboard_bridge-Server.py` | Flask API, browser interface, persistence, shared space and optional isolated accounts |
| Windows app | `clipboard_bridge_windows.py` | Tray commands, Tk history/settings, clipboard access, optional automation and embedded HTTP host |
| Shared Python text conversion | `clipboard_text.py` | Normalize copied rich text to plain Unicode; preserve actual files |
| Shared Python history storage | `clipboard_storage.py` | Refuse malformed/unreadable indices; flush and atomically commit complete replacements |
| Android app | `android/app/src/main/` | Native UI, server history, Share target, notifications and optional incoming monitoring |
| Apple integration | `Iphone Shortcuts/` | User-triggered Send and Receive Shortcuts for iPhone, iPad and Mac |

The Python entry points remain at the root intentionally: existing Docker recipes,
source download links and manual launch commands depend on those paths. A folder
cleanup must not silently become an application rewrite.

## Data Flow

1. The source client reads copied text, an image or a selection of files.
2. It uploads one history item to its configured host and optional account.
3. Other clients retrieve the newest item, manually or through supported automation.
4. A user can select an older history item to restore it, or delete it explicitly.

Newest means newest upload, not a preferred content type. Several files selected
together form one bundle; generic raw downloads use a transport ZIP. Unicode text
retains emoji, accents and line breaks. A document sent as a file keeps its bytes.
See the [API reference](../../README.md#api-reference) for payloads and endpoints.

## Boundaries And Constraints

- Windows uses a single Tk event loop; network work must not block it. Tray actions
  schedule UI work rather than creating competing Tk roots or event loops.
- Binary Windows clipboard writes share one checked buffer transfer. A message-only
  window belongs to the calling worker thread, not the Tk thread. Prepare and unlock
  memory before clearing the clipboard; transfer ownership only on API success.
  Clearing and setting are not atomic: a later set failure cannot restore old OS
  contents, but it must not advance the receive cursor or report success.
- Windows Server mode exposes the lightweight API and history, not a browser UI
  or multiple accounts. The standalone host supplies those additional features.
- Android incoming monitoring uses a user-enabled foreground service. Do not
  describe it as guaranteed delivery during device sleep or unrestricted clipboard
  access in other apps.
- Apple Shortcuts are user-triggered. They are not a background clipboard watcher.
- Keep existing shared-space, account and token URLs compatible with the Shortcuts.
  Authentication values in URLs are not encryption. Use a trusted LAN or private
  VPN; do not encourage direct public exposure of port 5088.

## Android Operation Boundaries

An action captures immutable connection settings, including an internal generation.
Group metadata and members use that same source. Checks before dispatch and before
accepting a result reject a superseded connection; they do not reroute an in-flight
operation. Changing away and back also advances the generation. Notification and
automation preferences do not change it.

Settings writes and the final clipboard/seen-ID update share a short in-process
gate. Network work and file copying do not hold that gate. A source change before
the clipboard update causes receipt to fail and attempts cleanup of the new files.
An already-sent upload/delete may still finish on the original host; there is no
remote transaction rollback. Existing optional account/token URLs are unchanged.

History and command responses have separate UI request tickets. Pause, superseding
refreshes and source changes invalidate old results; periodic refreshes do not pile
up while one is running. A history selection carries its original source through
download/delete confirmation. Testing draft Settings does not modify the active
configuration: only Save does. Device lifecycle and real clipboard behavior still
require the [manual acceptance checks](../../maintainer/MANUAL_TESTS.md).

## Directory Ownership

```text
clipboard_bridge-Server.py   Standalone server entry point
clipboard_bridge_windows.py Windows entry point and embedded host
clipboard_text.py           Shared text conversion
clipboard_storage.py        Shared history persistence
clipboard_updates.py        GitHub metadata, verified downloads and Windows helper
android/                    Android application and Gradle wrapper
Iphone Shortcuts/           Signed exports and update instructions
packaging/windows/          Installer definition and generated version metadata
scripts/                    Developer tools and scripts/windows/ build commands
tests/                      Python regression tests
docs/                       GitHub Pages, public visuals and development notes
maintainer/                 Manual test plans, release checks and media provenance
distribution/               Store adapter sources
.github/                    CI, ownership and issue/PR templates
```

`Dockerfile`, `compose.yaml`, the compatibility `docker-compose.yml`, dependency
files and `.env.example` stay at the root for standard container commands.
The [separate AppStore repository](https://github.com/Mattboxx/Clipboard-Bridge-AppStore)
publishes the current store catalogs; do not mistake a bundled adapter for the
live catalog.

`build/`, `dist/`, `Output/`, Python caches, local agent state, credentials and
runtime data are ignored local artifacts. They are not the published source tree.
Reorganizing the repository does not authorize deleting installed apps or builds.

## Build And Release Contract

`VERSION` is the source of truth for Windows metadata. Generate and validate it
with `python scripts/release_metadata.py --write --check`. Installer and portable
names remain stable; Android and the standalone server have separate versions.

See [Windows packaging](../../packaging/windows/README.md) for the moved build
commands. Tests must verify the new paths as well as actual source behavior.
Keep source files in Git and ready-to-use packages in Releases. Never include
private settings, signing keys or recordings of a personal desktop.

## Windows Update Boundary

The Settings controller uses background workers and one operation lock; no HTTP or
installer waits run on the Tk thread. Automatic checks are on, installation is
opt-in, and an open Settings window defers automatic restart. Only numeric stable
Windows releases and exact official x64/ARM64 asset names are eligible. HTTPS,
size/hash, embedded version and PE machine checks are mandatory. GitHub digests
are transport/integrity evidence, not a trusted publisher signature.

A copy of the current frozen EXE runs helper mode before tray, Tk or profile
migration initialization. It validates a bounded ticket in the private update
cache, verifies the parent process image, waits for exit and rechecks the payload
and target before replacement. It never kills the parent or other applications.
Portable replacement uses a backup; installer failure attempts EXE recovery.
Windows ShellExecute preserves security approval decisions. The helper restarts
the app and records a content-free result. No clipboard/account values enter the
GitHub request or ticket. Native CI upgrades the public 2.0.17 binary in disposable
profiles; this does not validate every interactive SmartScreen/Defender policy.

## Screenshots And Demos

The main READMEs show desktop visuals without requiring an expanded details panel.
Public media live under `docs/assets/`; the website and README reuse the same assets
instead of keeping duplicate copies with different privacy fixes.

- Use actual application captures and public sample data, not invented UI.
- Keep raw screen recordings private. Exclude credentials, account URLs, personal
  clipboard history, other applications and identifying desktop details.
- Distinguish a screenshot or tray-menu demonstration from a physical transfer test.
- Keep a static poster for reduced-motion viewers and a direct full-size media link.
- Record capture origin and editing in the maintainer notes. Existing sources:
  [Windows tray](../../maintainer/WINDOWS_TRAY_DEMO.md),
  [web demo](../../maintainer/WEB_DEMO.md), and
  [Apple illustrations](../../maintainer/APPLE_VISUAL_GUIDE.md).

## Validation

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for local setup and platform-specific
tests. CI validates server/API behavior, public site links, repository layout,
Windows behavior and Android builds. The native ARM64 workflow additionally checks
bundled PE architectures, the installer payload and configuration preservation.
Automated checks do not replace the pending device/network acceptance tests in
[MANUAL_TESTS.md](../../maintainer/MANUAL_TESTS.md).
