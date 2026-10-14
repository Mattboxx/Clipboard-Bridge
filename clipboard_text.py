"""Plain Unicode text for clipboard payloads, never for uploaded files."""

import re

from striprtf.striprtf import rtf_to_text


RTF_MIMES = frozenset({"text/rtf", "application/rtf", "application/x-rtf"})
_RTF_HEADER = re.compile(r"\A\ufeff?\s*\{\\rtf[1-9][0-9]*\b")
_FIELD_INSTRUCTION = re.compile(r"(?<!\\)((?:\\\\)*)\\fldinst\b")
_CODEPAGE = re.compile(rb"\\ansicpg([0-9]+)\b")


def decode_rtf_bytes(raw):
    """Decode unnamed RTF clipboard bodies using their declared ANSI code page."""
    if not raw.lstrip(b" \t\r\n").startswith(b"{\\rtf"):
        return None
    match = _CODEPAGE.search(raw[:4096])
    encoding = "cp" + match[1].decode("ascii") if match else "cp1252"
    try:
        return raw.decode(encoding, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def plain_clipboard_text(text):
    """Keep plain text unchanged; remove formatting from an RTF clipboard value."""
    if not _RTF_HEADER.match(text):
        return text
    document = text.lstrip("\ufeff \t\r\n")
    # Hide field instructions without adding hyperlink URLs to their visible labels.
    document = _FIELD_INSTRUCTION.sub(r"\1\\comment", document)
    try:
        plain = rtf_to_text(document, errors="replace")
        # RTF stores emoji as two UTF-16 units; join them into Unicode characters.
        return plain.encode("utf-16-le", errors="surrogatepass").decode(
            "utf-16-le", errors="replace"
        )
    except (ValueError, OverflowError, LookupError, TypeError):
        # Do not discard clipboard content if a producer sends malformed RTF.
        return text
