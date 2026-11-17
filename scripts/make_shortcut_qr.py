"""Regenerate the static QR codes of the public iCloud Shortcut links.

The website and READMEs show these SVG files; the server draws the same links
itself. Run this after changing an iCloud link in clipboard_bridge-Server.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import qrcode
from qrcode.image.svg import SvgPathFillImage

ROOT = Path(__file__).resolve().parents[1]
QR_DIR = ROOT / "docs" / "assets" / "qr"
NAMES = {"dl_send": "send-clipboard.svg", "dl_recv": "receive-clipboard.svg"}


def shortcut_links() -> dict[str, str]:
    source = (ROOT / "clipboard_bridge-Server.py").read_text(encoding="utf-8")
    pairs = re.findall(r'\("(dl_send|dl_recv)", "(https://www\.icloud\.com/shortcuts/[0-9a-f]{32})"\)', source)
    return dict(pairs)


def render(url: str) -> bytes:
    return qrcode.make(url, image_factory=SvgPathFillImage, box_size=10, border=2).to_string()


def main() -> None:
    QR_DIR.mkdir(parents=True, exist_ok=True)
    for label, url in shortcut_links().items():
        (QR_DIR / NAMES[label]).write_bytes(render(url))


if __name__ == "__main__":
    main()
