"""Preview IndexNow submissions; --submit notifies engines after deployment."""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
BASE = "https://mattboxx.github.io/Clipboard-Bridge/"
KEY = "73a0c6cf84f34cddad1e26859373c194"
ENDPOINT = "https://api.indexnow.org/indexnow"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def build_payload(root: Path = ROOT) -> dict:
    """Only public, canonical HTML pages from this project's sitemap are allowed."""
    docs = root / "docs"
    if (docs / f"{KEY}.txt").read_text(encoding="utf-8").strip() != KEY:
        raise ValueError("The published IndexNow key file does not match")
    sitemap = ET.parse(docs / "sitemap.xml")
    urls = [node.text.strip() for node in sitemap.findall("sm:url/sm:loc", NS)]
    if not urls or len(urls) != len(set(urls)) or len(urls) > 10_000:
        raise ValueError("Sitemap must contain 1-10000 distinct URLs")
    for url in urls:
        parsed = urlsplit(url)
        filename = url.removeprefix(BASE) or "index.html"
        if (not url.startswith(BASE) or parsed.query or parsed.fragment
                or not re.fullmatch(r"[a-z0-9.-]+\.html", filename)
                or not (docs / filename).is_file()):
            raise ValueError(f"Not a public project HTML page: {url}")
    return {"host": urlsplit(BASE).netloc, "key": KEY,
            "keyLocation": f"{BASE}{KEY}.txt", "urlList": urls}


def submit(payload: dict) -> int:
    """Verify the deployed ownership file before sending any notifications."""
    with urllib.request.urlopen(payload["keyLocation"], timeout=20) as response:
        if response.read(1024).decode("utf-8").strip() != KEY:
            raise ValueError("The live key file is missing or does not match")
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "ClipboardBridgeSiteUpdate/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        status = response.status
    if status not in (200, 202):
        raise ValueError(f"Unexpected IndexNow response: HTTP {status}")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submit", action="store_true", help="Send after Pages deployment")
    args = parser.parse_args()
    try:
        payload = build_payload()
        if not args.submit:
            print(json.dumps(payload, indent=2))
            print("Preview only. Use --submit after the site has deployed.")
            return
        status = submit(payload)
    except (ValueError, OSError, urllib.error.URLError, ET.ParseError) as exc:
        raise SystemExit(f"Search notification failed: {exc}") from exc
    print(f"IndexNow HTTP {status}: notification received; indexing is not guaranteed.")
    if status == 202:
        print("Ownership key validation is still pending.")


if __name__ == "__main__":
    main()
