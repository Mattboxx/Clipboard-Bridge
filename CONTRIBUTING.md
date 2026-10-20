# Contributing

Thanks for helping improve Clipboard Bridge. Keep changes focused, testable and
compatible with the two supported operating modes.

Start with the [architecture and repository map](docs/development/ARCHITECTURE.md).
Build commands live in [scripts/](scripts/README.md); Windows installer sources live
in [packaging/windows/](packaging/windows/README.md). User instructions stay in the
root README, GUIDE and DOCKER documents; `docs/` also contains the public website.

Main requires a pull request and passing Python/Windows/Android checks. Read the
[repository protection policy](maintainer/REPOSITORY_POLICY.md) before changing CI
job names or preparing a release; successful CI does not replace maintainer approval.

## Development setup

Use Python 3.12 on Windows for the client and any Python 3.12 environment for the
server. Native Windows ARM64 builds use ARM64 Python 3.13.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-server.txt -r requirements-client.txt pytest
python -m pytest -q
```

Run the server with:

```powershell
python clipboard_bridge-Server.py
```

Run the Windows client with:

```powershell
python clipboard_bridge_windows.py
```

## Windows release builds

Release attachments are for end users: Windows installers/portable executables,
the signed Android APK and the two signed iPhone Shortcuts. Keep Python scripts
and other developer sources in the repository, not as release attachments.
Publish download checksums in the release notes.

`scripts\windows\build_release.bat` builds the x64 portable executable and installer.
It rejects non-x64 Python to avoid incorrectly labeled packages.
`scripts\windows\build_client.bat` builds a development portable executable only.
Both commands locate the repository root automatically, even when launched from
another working directory. Run `python scripts/release_metadata.py --write --check`
after changing `VERSION`; generated metadata belongs in `packaging/windows/`.

Both scripts install the pinned `requirements-build.txt` toolchain and respect the
active virtual environment. `PYTHON_EXE` can explicitly select another interpreter.
Release staging preserves extra files; see [folder ownership and failure behavior](packaging/windows/README.md#release-folder-ownership).
The **Build Windows x64** workflow executes the actual batch script, validates the
native portable and installed payloads, and checks preservation of seeded settings
and histories on an ephemeral runner. Its `clipboard-bridge-windows-x64` artifact
also records checksums, resolved dependencies and build provenance. It is not a
public release or a substitute for physical standard-user/upgrade acceptance.

For native Windows ARM64, run the **Build Windows ARM64** GitHub Actions workflow.
It uses a native `windows-11-arm` runner and ARM64 Python, not cross-compilation or
an x64 executable renamed as ARM64. The workflow runs the client tests, verifies
the PE architecture of every bundled DLL/PYD (including PDFium), checks the frozen
application's local server and single-instance behavior, and installs the package
to verify its payload and configuration preservation. The verified executables
are available in its `clipboard-bridge-windows-arm64` artifact.

Only publish those executables after the entire workflow succeeds. Keep ARM64 and
x64 download names distinct. Both installers use the same application identity,
so changing architecture preserves the existing per-user settings and history.

## Pull requests

- Open an issue first for large changes or changes to the API.
- Preserve compatibility with the prepared iOS Shortcuts.
- Add or update focused tests for behavior changes.
- Keep user data under the configured writable data directories.
- Do not commit real clipboard data, credentials, local configuration or build
  output.
- Update English and Italian documentation when user-facing behavior changes.
- For desktop documentation, use real captures with an isolated profile and public
  sample data. Never capture a personal history or connection settings. Follow the
  [media provenance rules](docs/development/ARCHITECTURE.md#screenshots-and-demos).
- Run `python scripts/release_metadata.py --check` and `python -m pytest -q`
  before submitting.

Security reports must follow [SECURITY.md](SECURITY.md), not a public issue.

## Android Transfer Tests

With Java 17 and Android SDK 35 available, run from `android/`:

```powershell
.\gradlew.bat testDebugUnitTest assembleDebug lintDebug
```

On POSIX shells use `./gradlew` instead. `ApiClientTransferTest` exercises the real
HTTP client against a disposable loopback MockWebServer, including truncated streams,
group rollback, text/file discrimination, Unicode and invalid server responses. It
does not contact a personal server or use a device clipboard. MockWebServer and the
JVM JSON implementation are test-only dependencies, not additions to the release APK.

`ReceivedFilesTest` separately injects create/write/publish/clipboard failures through
an in-memory destination. It verifies the receive operation's ordering, cleanup,
preservation of existing files and behavior when a provider refuses deletion. The
Android adapter uses [MediaStore's pending flag](https://developer.android.com/reference/android/provider/MediaStore.MediaColumns#IS_PENDING)
and checks the updated-row count before claiming publication. Multiple rows and the
system clipboard do not form an atomic Android transaction: rollback is best effort,
and process termination or provider deletion failures can leave files behind.

These tests do not establish Android MediaStore, clipboard permissions, Quick Settings
or sleep/background behavior. Complete the physical-device cases in
[the manual acceptance plan](maintainer/MANUAL_TESTS.md) before claiming those results.

`ApiClientConnectionTest` changes accounts/servers while the actual HTTP client is
waiting for responses. It checks that group members are never rerouted, stale
downloads are discarded and old acknowledgements cannot mark a new account as seen.
`AppConfigConnectionTest` uses in-memory preferences to exercise source generations,
legacy settings, cursor resets and the short commit gate shared by Settings and
clipboard application. `ConnectionRequestGateTest` checks UI request invalidation;
it does not instantiate an Android Activity or prove the rendered lifecycle behavior.

The generation protects in-process ordering, not disk durability or a multi-process
transaction. The application keeps the existing
[SharedPreferences `apply()` behavior](https://developer.android.com/reference/android/content/SharedPreferences.Editor#apply()):
memory changes become available before its asynchronous disk write. Network requests
and copying file bytes remain outside the commit gate. An already-sent request may
still finish on its original host; changing Settings cannot undo that remote action.

## Disposable Container Integration

Build a local test image, then opt in to real HTTP/persistence tests:

```powershell
docker build -t clipboard-bridge-server:test .
$env:CLIPBOARD_TEST_IMAGE = "clipboard-bridge-server:test"
python -m pytest -q tests/test_container.py
```

On POSIX shells, use `CLIPBOARD_TEST_IMAGE=clipboard-bridge-server:test python -m
pytest -q tests/test_container.py` instead of the PowerShell environment assignment.
The suite creates uniquely named containers and volumes, binds a dynamic port to
localhost and removes only those test resources. It never mounts an existing data
directory or uses a production container. Docker must be running.

These checks exercise transfers, groups, accounts, upload limits, remembered web
sessions, restart/recreation, damaged-index protection and restoration. Windows
also runs the native client protocol assertions against this disposable host;
Linux skips only that Windows-specific check. CI executes the container suite
after building the server image.

`tests/test_live_server.py` remains available for an explicitly isolated external
test host through `CLIPBOARD_TEST_SERVER_URL`; do not point it at a personal or
production instance. Set `CLIPBOARD_TEST_SERVER_VERSION` to additionally assert a
specific version. The disposable suite is the safer default.
