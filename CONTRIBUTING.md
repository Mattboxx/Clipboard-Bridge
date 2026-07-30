# Contributing

Thanks for helping improve Clipboard Bridge. Keep changes focused, testable and
compatible with the two supported operating modes.

## Development setup

Use Python 3.12 on Windows for the client and any Python 3.12 environment for the
server.

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

## Pull requests

- Open an issue first for large changes or changes to the API.
- Preserve compatibility with the prepared iOS Shortcuts.
- Add or update focused tests for behavior changes.
- Keep user data under the configured writable data directories.
- Do not commit real clipboard data, credentials, local configuration or build
  output.
- Update English and Italian documentation when user-facing behavior changes.
- Run `python scripts/release_metadata.py --check` and `python -m pytest -q`
  before submitting.

Security reports must follow [SECURITY.md](SECURITY.md), not a public issue.
