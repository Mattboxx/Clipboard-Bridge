# Contributing

Thanks for helping improve Clipboard Bridge. Keep changes focused, testable and
compatible with the two supported operating modes.

Start with the [architecture and repository map](docs/development/ARCHITECTURE.md).
Build commands live in [scripts/](scripts/README.md); Windows installer sources live
in [packaging/windows/](packaging/windows/README.md). User instructions stay in the
root README, GUIDE and DOCKER documents; `docs/` also contains the public website.

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
