# Developer Commands

Run Python commands from the repository root. Windows batch scripts find the root
from their own location, regardless of the caller's working directory.

| Command | Purpose | Output |
| --- | --- | --- |
| `python scripts/release_metadata.py --check` | Check version metadata and release references | No file changes |
| `python scripts/release_metadata.py --write --check` | Regenerate executable version metadata | `packaging/windows/windows_version_info.txt` |
| `scripts\windows\build_client.bat` | Build an x64 development portable client | `dist/Clipboard Bridge.exe` |
| `scripts\windows\build_release.bat` | Build x64 portable and installer packages | `dist/` and `Output/` |
| `python scripts/prepare_release_assets.py` | Stage existing local x64 packages, Apple exports and an optional release APK | Versioned folder under `Output/`; keeps previously added files |
| `python scripts/verify_windows_build.py EXE --architecture x64 --smoke` | Verify a frozen x64 payload and run an isolated smoke test | Validation output |
| `python scripts/notify_search_engines.py` | Preview public discovery URLs | No submission by default |

Use `--architecture arm64` to verify a native ARM64 payload. Build ARM64 packages
with the **Build Windows ARM64** GitHub Actions workflow. The verification script
requires PyInstaller; smoke tests use a disposable profile rather than personal
settings or clipboard contents.

The **Build Windows x64** workflow runs the actual release batch script and checks
the portable/installed payloads on a disposable runner. Its artifact is
`clipboard-bridge-windows-x64`; it is a development build, not a published release.
The scripts share `requirements-build.txt`, respect an active virtual environment
and accept `PYTHON_EXE` as an explicit interpreter override.

Staging validates required sources first and finishes temporary copies before
publishing them. The optional APK needs its matching Gradle `output-metadata.json`.
Publication is atomic per file, not across the entire folder: a late replacement
failure can leave a partial new set and must stop release publication. Extra files
are preserved, not certified. See [packaging details](../packaging/windows/README.md).

The old root build scripts now live under `scripts/windows/`. No executable or
local application data was removed during that reorganization.

See [contributing](../CONTRIBUTING.md), [Windows packaging](../packaging/windows/README.md)
and [search discovery notes](../maintainer/SEARCH_DISCOVERY.md) for prerequisites
and publication checks. Do not run release publication or search submission as a
side effect of ordinary tests.
