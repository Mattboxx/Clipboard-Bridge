"""Create and validate release metadata from the root VERSION file."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def current_version() -> str:
    version = VERSION_FILE.read_text(encoding="ascii").strip()
    if not VERSION_PATTERN.fullmatch(version):
        raise SystemExit(f"Invalid version in {VERSION_FILE}: {version!r}")
    return version


def version_tuple(version: str) -> str:
    return ", ".join((*version.split("."), "0"))


def version_info(version: str) -> str:
    numeric = version_tuple(version)
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({numeric}),
    prodvers=({numeric}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Clipboard Bridge'),
          StringStruct('FileDescription', 'Clipboard Bridge Windows client'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'Clipboard Bridge'),
          StringStruct('LegalCopyright', 'Copyright (c) 2026 Clipboard Bridge contributors'),
          StringStruct('OriginalFilename', 'Clipboard Bridge.exe'),
          StringStruct('ProductName', 'Clipboard Bridge'),
          StringStruct('ProductVersion', '{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def write_metadata(version: str) -> None:
    (ROOT / "windows_version_info.txt").write_text(
        version_info(version),
        encoding="utf-8",
        newline="\n",
    )


def check_contains(path: Path, values: list[str]) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [value for value in values if value not in text]


def validate(version: str) -> None:
    errors = []
    generated = version_info(version)
    actual = (ROOT / "windows_version_info.txt").read_text(encoding="utf-8")
    if actual.replace("\r\n", "\n") != generated:
        errors.append("windows_version_info.txt was not generated from VERSION")

    release_files = {
        ROOT / "README.md": [f"Windows {version}", f"/releases/tag/{version}"],
        ROOT / "README.it.md": [f"Windows {version}", f"/releases/tag/{version}"],
        ROOT / "GUIDE.md": [f"Clipboard Bridge {version} release"],
        ROOT / "docs" / "index.html": [
            f"Download Clipboard Bridge {version}",
            f"/releases/download/{version}/",
        ],
    }
    for path, values in release_files.items():
        for missing in check_contains(path, values):
            errors.append(f"{path.relative_to(ROOT)} is missing {missing!r}")

    if errors:
        raise SystemExit("\n".join(f"ERROR: {error}" for error in errors))

    print(f"Release metadata {version}: OK")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="regenerate version metadata")
    parser.add_argument("--check", action="store_true", help="validate release references")
    args = parser.parse_args()
    version = current_version()
    if args.write:
        write_metadata(version)
    if args.check:
        validate(version)
    if not args.write and not args.check:
        print(version)


if __name__ == "__main__":
    main()
