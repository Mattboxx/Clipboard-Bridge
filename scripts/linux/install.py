#!/usr/bin/env python3
"""Install Clipboard Bridge for the current Linux user."""

import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_ID = "io.github.mattbox03.clipboard-bridge"
FILES = ("clipboard_bridge_linux.py", "clipboard_linux_transport.py", "clipboard_setup.py",
         "LICENSE", "LICENSE-MIT-legacy.txt",
         "THIRD_PARTY_NOTICES.md")


def exec_arg(value):
    value = str(value)
    if any(ord(ch) < 32 for ch in value):
        raise ValueError("Unsupported control character in installation path.")
    escaped = "".join("\\" + ch if ch in '\\"$`' else ch for ch in value)
    return '"' + escaped.replace("\\", "\\\\").replace("%", "%%") + '"'


def install(data_home, executable):
    app = data_home / APP_ID
    menu = data_home / "applications"
    launcher = menu / f"{APP_ID}.desktop"
    desktop = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Clipboard Bridge\n"
        "Comment=Share your clipboard and files\n"
        f"Exec={exec_arg(executable)} {exec_arg(app / FILES[0])}\n"
        f"Icon={str(app / 'icon.svg').replace(chr(92), chr(92) * 2)}\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
    )
    app.mkdir(parents=True, exist_ok=True)
    menu.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copy2(ROOT / name, app / name)
    shutil.copy2(ROOT / "docs" / "icon.svg", app / "icon.svg")
    launcher.write_text(desktop, encoding="utf-8")
    return launcher


def main():
    if not sys.platform.startswith("linux") or sys.version_info < (3, 10):
        sys.exit("Run this installer on Linux with Python 3.10 or newer.")
    if os.geteuid() == 0:
        sys.exit("Run this installer as your regular desktop user, without sudo.")
    try:
        import tkinter  # noqa: F401
    except ImportError:
        sys.exit("Install Tkinter for your Python interpreter, then rerun this installer.")
    base = Path(os.environ.get("XDG_DATA_HOME", ""))
    if not base.is_absolute():
        base = Path.home() / ".local" / "share"
    launcher = install(base, sys.executable)
    print(f"Installed Clipboard Bridge. Launch it from your application menu.\n{launcher}")


if __name__ == "__main__":
    main()
