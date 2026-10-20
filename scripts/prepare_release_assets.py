"""Stage local release assets without deleting files already added by the maintainer."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger("clipboard_bridge.release")
VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+")
ANDROID_VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9._+-]+)?")


def asset_plan(root: Path, version: str) -> list[tuple[Path, str]]:
    actual = (root / "VERSION").read_text(encoding="ascii").strip()
    if not VERSION_PATTERN.fullmatch(version) or version != actual:
        raise ValueError("Requested release version does not match VERSION.")
    names = (f"Clipboard.Bridge.Portable.Windows.x64.V{version}.exe",
             f"Clipboard.Bridge_windows_client_and_server_setup_x64_V{version}.exe")
    assets = [(root / "Output" / name, name) for name in names]
    assets.extend([
        (root / "Iphone Shortcuts/Load Clipboard.shortcut", "iPhone.Load.Clipboard.shortcut"),
        (root / "Iphone Shortcuts/Download Clipboard.shortcut", "iPhone.Download.Clipboard.shortcut"),
    ])
    apk = root / "android/app/build/outputs/apk/release/app-release.apk"
    if apk.exists():
        metadata = json.loads(apk.with_name("output-metadata.json").read_text(encoding="utf-8"))
        if (not isinstance(metadata, dict) or
                metadata.get("applicationId") != "io.github.mattbox03.clipboardbridge" or
                metadata.get("variantName") != "release"):
            raise ValueError("Android output metadata must identify the Clipboard Bridge release build.")
        elements = metadata.get("elements")
        if not isinstance(elements, list) or len(elements) != 1 or not isinstance(elements[0], dict):
            raise ValueError("Android output metadata must contain one universal APK.")
        element = elements[0]
        android_version = element.get("versionName")
        if element.get("filters") != [] or element.get("outputFile") != apk.name:
            raise ValueError("Android output metadata does not describe the universal release APK.")
        if not isinstance(android_version, str) or not ANDROID_VERSION_PATTERN.fullmatch(android_version):
            raise ValueError("Android output metadata has an unsupported version name.")
        assets.append((apk, f"Clipboard.Bridge.Android.universal.V{android_version}.apk"))
    for source, _ in assets:
        if not source.is_file() or source.stat().st_size == 0:
            raise ValueError(f"Missing or empty release asset: {source.relative_to(root)}")
    return assets


def prepare_release(root: Path, version: str) -> list[Path]:
    root = root.resolve()
    assets = asset_plan(root, version)
    destination = root / "Output" / f"Clipboard.Bridge.Release.V{version}"
    if destination.resolve() != destination:
        raise ValueError("Release staging must use an unlinked directory inside the project.")
    for _, name in assets:
        if (destination / name).is_dir():
            raise ValueError(f"A directory occupies the release filename: {name}")
    destination.mkdir(parents=True, exist_ok=True)
    staged = []
    try:
        # Finish all copies before replacing any existing managed asset.
        for source, name in assets:
            with tempfile.NamedTemporaryFile(mode="wb", prefix=".clipboard-release-", suffix=".tmp",
                                             dir=destination, delete=False) as output:
                temporary = Path(output.name)
                staged.append((temporary, destination / name))
                with source.open("rb") as input_file:
                    shutil.copyfileobj(input_file, output)
                output.flush()
                os.fsync(output.fileno())
        for temporary, target in staged:
            os.replace(temporary, target)
    finally:
        for temporary, _ in staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                LOG.warning("Could not remove a temporary release staging file.")
    return [target for _, target in staged]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="must match the root VERSION file")
    arguments = parser.parse_args()
    try:
        version = arguments.version or (ROOT / "VERSION").read_text(encoding="ascii").strip()
        assets = prepare_release(ROOT, version)
    except (OSError, ValueError) as error:
        print(f"ERROR: Release preparation failed: {error}", file=sys.stderr)
        return 1
    print(f"Staged {len(assets)} local assets; existing additional files were preserved.")
    print("Verify all intended release assets before publishing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
