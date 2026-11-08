#!/usr/bin/env python3
"""Build the architecture-independent Ubuntu/Debian preview package."""

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from install import APP_ID, FILES, ROOT


VERSION = "0.1.0-preview.1"
DEB_VERSION = VERSION.replace("-preview.", "~preview.")
PACKAGE = "clipboard-bridge"
ASSET = f"Clipboard.Bridge.Ubuntu.V{VERSION}.all.deb"


def write(root, relative, content, mode=0o644):
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    destination.chmod(mode)


def copy(root, source, relative):
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / source, destination)
    destination.chmod(0o644)


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="clipboard-bridge-deb-") as temporary:
        root = Path(temporary) / "package"
        write(root, "DEBIAN/control", f"""Package: {PACKAGE}
Version: {DEB_VERSION}
Architecture: all
Section: utils
Priority: optional
Maintainer: Clipboard Bridge contributors <26332097+Mattboxx@users.noreply.github.com>
Depends: python3 (>= 3.10), python3-tk, xdg-utils, wl-clipboard | xclip
Recommends: wl-clipboard, xclip, python3-pil, poppler-utils
Homepage: https://mattboxx.github.io/Clipboard-Bridge/
Description: Share clipboard text and files between devices
 Graphical Linux client for a Clipboard Bridge Docker server or a Windows
 Clipboard Bridge host. This package is an early desktop preview.
""")
        write(root, "usr/bin/clipboard-bridge",
              '#!/bin/sh\nexec /usr/bin/python3 -B /usr/lib/clipboard-bridge/clipboard_bridge_linux.py "$@"\n',
              0o755)
        write(root, f"usr/share/applications/{APP_ID}.desktop", f"""[Desktop Entry]
Type=Application
Name=Clipboard Bridge
Comment=Share clipboard text and files
Exec=clipboard-bridge
Icon={APP_ID}
Terminal=false
Categories=Utility;
""")
        for name in FILES:
            directory = "usr/lib/clipboard-bridge" if name.endswith(".py") else "usr/share/doc/clipboard-bridge"
            copy(root, name, f"{directory}/{name}")
        copy(root, "docs/icon.svg", f"usr/share/icons/hicolor/scalable/apps/{APP_ID}.svg")
        write(root, "usr/share/doc/clipboard-bridge/copyright",
              "Clipboard Bridge contributors. GPL-3.0-only; see LICENSE, the preserved legacy notice,\n"
              "and THIRD_PARTY_NOTICES.md in this directory.\n")
        for directory, _, _ in os.walk(root):
            Path(directory).chmod(0o755)
        result = output / ASSET
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(root), str(result)], check=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "Output" / "linux-release")
    args = parser.parse_args()
    print(build(args.out.resolve()))


if __name__ == "__main__":
    main()
