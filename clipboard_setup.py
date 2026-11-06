"""Public setup information. No passwords, tokens or keys are embedded in QR codes."""

import re
from urllib.parse import urlsplit

DOWNLOAD_URL = "https://mattboxx.github.io/Clipboard-Bridge/#download"


def base_address(value):
    value = value.strip()
    if not value or any(ord(c) < 33 or c in "\\?#%@" for c in value):
        raise ValueError("Enter a server address without a path, password or query.")
    parsed = urlsplit(value if "://" in value else "http://" + value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.path not in ("", "/") or parsed.netloc.endswith(":")
            or not parsed.netloc.isascii() or not re.fullmatch(r"[a-zA-Z0-9.\-:\[\]]+", parsed.netloc)
            or parsed.port == 0):
        raise ValueError("Enter a server address without a path, password or query.")
    return f"{parsed.scheme}://{parsed.netloc.lower()}"
