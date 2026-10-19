# Developer Commands

Run Python commands from the repository root. Windows batch scripts find the root
from their own location, regardless of the caller's working directory.

| Command | Purpose | Output |
| --- | --- | --- |
| `python scripts/release_metadata.py --check` | Check version metadata and release references | No file changes |
| `python scripts/release_metadata.py --write --check` | Regenerate executable version metadata | `packaging/windows/windows_version_info.txt` |
| `scripts\windows\build_client.bat` | Build an x64 development portable client | `dist/Clipboard Bridge.exe` |
| `scripts\windows\build_release.bat` | Build x64 portable and installer packages | `dist/` and `Output/` |
| `python scripts/verify_windows_build.py EXE --architecture x64 --smoke` | Verify a frozen x64 payload and run an isolated smoke test | Validation output |
| `python scripts/notify_search_engines.py` | Preview public discovery URLs | No submission by default |

Use `--architecture arm64` to verify a native ARM64 payload. Build ARM64 packages
with the **Build Windows ARM64** GitHub Actions workflow. The verification script
requires PyInstaller; smoke tests use a disposable profile rather than personal
settings or clipboard contents.

The old root build scripts now live under `scripts/windows/`. No executable or
local application data was removed during that reorganization.

See [contributing](../CONTRIBUTING.md), [Windows packaging](../packaging/windows/README.md)
and [search discovery notes](../maintainer/SEARCH_DISCOVERY.md) for prerequisites
and publication checks. Do not run release publication or search submission as a
side effect of ordinary tests.
