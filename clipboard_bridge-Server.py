#!/usr/bin/env python3
"""
Clipboard Bridge - Server
=========================

HTTP server (Flask) for the clipboard between Windows, Android and Apple devices
(through Apple Shortcuts).

Features:
  - Text, images and generic files
  - History of N items, files stored on disk + index.json
  - "raw" endpoints made for Shortcuts (text as text/plain, images as binary)
  - Optional token to protect the server (X-Auth-Token header or ?token=...)

Start:
    pip install -r requirements-server.txt
    python clipboard_bridge-Server.py

Configuration via environment variables (all optional):
    CLIPBOARD_PORT          listening port           (default 5088)
    CLIPBOARD_TOKEN         security token           (default: empty = no auth)
    CLIPBOARD_PASSWORD      shared web password      (default: empty)
    CLIPBOARD_ACCOUNTS      extra user:password pairs
    CLIPBOARD_ACCOUNTS_FILE path to an accounts file
    CLIPBOARD_SESSION_DAYS  remembered web login      (default 3650)
    CLIPBOARD_MAX_HISTORY   max history items        (default 200)
    CLIPBOARD_MAX_UPLOAD_MB max request size in MB   (default 64)
    CLIPBOARD_DATA_DIR      data folder              (default ./clipboard_data)

Example with a token (PowerShell):
    $env:CLIPBOARD_TOKEN="mysecret"; python clipboard_bridge-Server.py
"""

from flask import Flask, request, jsonify, Response, send_file, redirect, session, g
from markupsafe import escape
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge
from werkzeug.http import parse_options_header
from urllib.parse import quote, unquote, urlencode
import base64
import hmac
import io
import os
import json
import re
import time
import uuid
import mimetypes
import threading
import zipfile
from functools import lru_cache
from datetime import datetime, timedelta
from clipboard_text import RTF_MIMES, decode_rtf_bytes, plain_clipboard_text
from clipboard_storage import HistoryStoreError, read_history, write_history
from clipboard_setup import DOWNLOAD_URL, base_address
import qrcode
from qrcode.image.svg import SvgPathImage

app = Flask(__name__)

# ---------- Configuration ----------
SERVER_VERSION = "1.0.12"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("CLIPBOARD_DATA_DIR", os.path.join(BASE_DIR, "clipboard_data"))
ITEMS_DIR = os.path.join(DATA_DIR, "items")
INDEX_FILE = os.path.join(DATA_DIR, "index.json")
PUBLIC_ADDRESS = os.getenv("CLIPBOARD_PUBLIC_ADDRESS", "")
if PUBLIC_ADDRESS:
    PUBLIC_ADDRESS = base_address(PUBLIC_ADDRESS)


def _env_int(name, default, minimum, maximum):
    """Read a bounded integer without making the server fail on a bad setting."""
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


PORT = _env_int("CLIPBOARD_PORT", 5088, 1, 65535)
AUTH_TOKEN = os.environ.get("CLIPBOARD_TOKEN", "").strip()      # API token for the GENERAL/shared space
WEB_PASSWORD = os.environ.get("CLIPBOARD_PASSWORD", "").strip()  # web password for the GENERAL space
MAX_HISTORY = _env_int("CLIPBOARD_MAX_HISTORY", 200, 1, 100000)
MAX_UPLOAD_MB = _env_int("CLIPBOARD_MAX_UPLOAD_MB", 64, 1, 1024)
_ACCOUNT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def _parse_accounts(raw):
    """Parse "user1:pass1,user2:pass2" into {name: password}.

    Accepts both commas and newlines as separators, so the same parser works
    for the CLIPBOARD_ACCOUNTS variable and for a one-per-line accounts file.
    Lines starting with '#' are treated as comments. No limit on the count.
    """
    accounts = {}
    for part in (raw or "").replace("\r", "\n").replace("\n", ",").split(","):
        part = part.strip()
        if not part or part.startswith("#"):
            continue
        if ":" in part:
            name, pw = part.split(":", 1)
            name = name.strip()
            if _ACCOUNT_NAME.fullmatch(name):
                accounts[name] = pw
    return accounts


# Extra accounts (besides the always-available general space). Each one has its own
# isolated history, stored under DATA_DIR/users/<name>/. There is no limit on how many
# accounts can be defined. For many users, prefer CLIPBOARD_ACCOUNTS_FILE (one
# "user:password" per line) over the inline CLIPBOARD_ACCOUNTS variable.
ACCOUNTS = _parse_accounts(os.environ.get("CLIPBOARD_ACCOUNTS", ""))
_ACCOUNTS_FILE = os.environ.get("CLIPBOARD_ACCOUNTS_FILE", "").strip()
if _ACCOUNTS_FILE and os.path.isfile(_ACCOUNTS_FILE):
    with open(_ACCOUNTS_FILE, encoding="utf-8") as _f:
        ACCOUNTS.update(_parse_accounts(_f.read()))   # file entries extend / override


def _account_alias_groups(accounts):
    """Preselect possible filesystem aliases without scanning every user per request."""
    groups = {}
    for name in accounts:
        groups.setdefault(name.casefold().rstrip("."), []).append(name)
    return groups


_ACCOUNT_ALIASES = _account_alias_groups(ACCOUNTS)


class AccountStorageError(RuntimeError):
    def __init__(self, reason):
        self.reason = reason
        message = (
            "Account storage is ambiguous on this filesystem. "
            "Ask the administrator to review account names; existing data was not changed."
            if reason == "alias" else
            "Account storage is unavailable. Ask the administrator to check its permissions and configuration."
        )
        super().__init__(message)


os.makedirs(ITEMS_DIR, exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

# Persistent secret key so login sessions survive server restarts.
_key_path = os.path.join(DATA_DIR, "secret.key")
try:
    with open(_key_path, "rb") as _kf:
        app.secret_key = _kf.read()
    if len(app.secret_key) < 32:
        raise OSError("invalid secret key")
except OSError:
    app.secret_key = os.urandom(32)
    try:
        with open(_key_path, "wb") as _kf:
            _kf.write(app.secret_key)
    except OSError:
        pass
if os.name != "nt":
    try:
        os.chmod(_key_path, 0o600)
    except OSError:
        pass
SESSION_DAYS = _env_int("CLIPBOARD_SESSION_DAYS", 3650, 1, 3650)
app.permanent_session_lifetime = timedelta(days=SESSION_DAYS)

_lock = threading.RLock()


# ---------- Accounts / per-request data location ----------
# Each request works on one space: the general/shared one (DATA_DIR) or an account's
# own folder (DATA_DIR/users/<name>). The current paths live on Flask's request `g`.
def _items_dir():
    return getattr(g, "items_dir", ITEMS_DIR)


def _index_file():
    return getattr(g, "index_file", INDEX_FILE)


def _use_general():
    g.account = None
    g.items_dir = ITEMS_DIR
    g.index_file = INDEX_FILE


def _use_account(name):
    base = os.path.join(DATA_DIR, "users", name)
    items = os.path.join(base, "items")
    try:
        os.makedirs(items, exist_ok=True)
        for other in _ACCOUNT_ALIASES[name.casefold().rstrip(".")]:
            if other == name:
                continue
            try:
                aliased = os.path.samefile(base, os.path.join(DATA_DIR, "users", other))
            except FileNotFoundError:
                continue
            if aliased:
                raise AccountStorageError("alias")
    except OSError as error:
        raise AccountStorageError("unavailable") from error
    g.account = name
    g.items_dir = items
    g.index_file = os.path.join(base, "index.json")


def _same_secret(first, second):
    """Compare user-provided secrets without early-exit timing differences."""
    return hmac.compare_digest(
        str(first or "").encode("utf-8"), str(second or "").encode("utf-8")
    )


# ---------- Index / history management ----------
def _history_page(items, params):
    query = (params.get("q") or "").strip()
    kind = params.get("type") or ""
    if len(query) > 200 or kind not in ("", "text", "image", "file", "bundle"):
        raise ValueError("invalid history search or type")
    try:
        offset = int(params.get("offset", 0))
        limit = int(params["limit"]) if "limit" in params else None
    except (TypeError, ValueError):
        raise ValueError("invalid history limit or offset") from None
    if offset < 0 or (limit is not None and not 1 <= limit <= 1000):
        raise ValueError("history limit must be 1-1000 and offset must be nonnegative")
    query = query.casefold()
    filtered = []
    for item in items:
        if kind and item.get("type") != kind:
            continue
        names = " ".join(member.get("filename") or "" for member in item.get("files", []))
        searchable = " ".join((item.get("preview") or "", item.get("filename") or "", names))
        if not query or query in searchable.casefold():
            filtered.append(item)
    page = filtered[offset:offset + limit] if limit is not None else filtered[offset:]
    return {"items": page, "count": len(page), "total": len(filtered),
            "offset": offset, "has_more": offset + len(page) < len(filtered)}


def _load_index():
    return read_history(_index_file())


def _save_index(index):
    write_history(_index_file(), index)


def _trim(index):
    """Detach expired entries; delete their files only after the index is committed."""
    expired = index[MAX_HISTORY:]
    del index[MAX_HISTORY:]
    return expired


def _commit_entry(entry):
    with _lock:
        try:
            index = _load_index()
            index.insert(0, entry)
            expired = _trim(index)
            _save_index(index)
        except Exception:
            _delete_entry_files(entry)
            raise
        for old in expired:
            _delete_entry_files(old)
    return entry


def _write_item(filename, payload):
    path = os.path.join(_items_dir(), filename)
    try:
        with open(path, "wb") as stream:
            stream.write(payload)
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise


def _stored_files(entry):
    """Return every internal filename owned by an index entry."""
    if entry.get("type") == "bundle":
        return [item.get("file") for item in entry.get("files", []) if item.get("file")]
    return [entry["file"]] if entry.get("file") else []


def _delete_entry_files(entry):
    for filename in _stored_files(entry):
        try:
            os.remove(os.path.join(_items_dir(), filename))
        except OSError:
            pass


def _public_bundle_files(entry):
    return [
        {
            "index": index,
            "filename": item.get("filename"),
            "mime": item.get("mime"),
            "size": item.get("size", 0),
            "type": item.get("type", "file"),
        }
        for index, item in enumerate(entry.get("files", []))
    ]


def _meta(entry):
    """Return only an item's metadata (without the content)."""
    out = {k: entry.get(k) for k in
           ("id", "type", "timestamp", "filename", "mime", "size", "preview")}
    if entry.get("type") == "bundle":
        out["file_count"] = len(entry.get("files", []))
        out["files"] = _public_bundle_files(entry)
    return out


def _read_text(entry):
    path = os.path.join(_items_dir(), entry["file"])
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", newline="") as f:
            return plain_clipboard_text(f.read())
    return ""


def _entry_with_content(entry):
    """Metadata + content: 'text' for text, 'data' (base64) for binaries."""
    out = _meta(entry)
    if entry["type"] == "text":
        out["text"] = _read_text(entry)
    elif entry["type"] == "bundle":
        # Bundle members have dedicated raw endpoints so JSON metadata stays small.
        pass
    else:
        path = os.path.join(_items_dir(), entry["file"])
        with open(path, "rb") as f:
            out["data"] = base64.b64encode(f.read()).decode()
    return out


def _latest_of(types):
    for e in _load_index():
        if e["type"] in types:
            return e
    return None


def _add_text(text):
    text = plain_clipboard_text(text)
    entry_id = uuid.uuid4().hex[:12]
    fname = entry_id + ".txt"
    _write_item(fname, text.encode("utf-8"))
    entry = {
        "id": entry_id,
        "type": "text",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ts": time.time(),
        "file": fname,
        "filename": None,
        "mime": "text/plain",
        "size": len(text.encode("utf-8")),
        "preview": text[:140],
    }
    return _commit_entry(entry)


def _clean_filename(filename):
    """Return a safe display filename while preserving Unicode and spaces."""
    if filename is None:
        return None
    filename = str(filename).replace("\\", "/").rsplit("/", 1)[-1]
    filename = "".join(ch for ch in filename if ch >= " " and ch not in "\r\n\x7f").strip()
    return filename[:240] or None


def _clean_mime(mime):
    if not mime:
        return None
    mime = str(mime).split(";", 1)[0].strip().lower()
    return mime or None


def _storage_extension(orig_filename, mime):
    if orig_filename:
        candidate = os.path.splitext(orig_filename)[1]
        if len(candidate) <= 32 and re.fullmatch(r"\.[A-Za-z0-9._+-]+", candidate or ""):
            return candidate.lower()
    if mime:
        return mimetypes.guess_extension(mime) or ""
    return ""


def _add_binary(raw, orig_filename=None, mime=None):
    orig_filename = _clean_filename(orig_filename)
    mime = _clean_mime(mime)
    entry_id = uuid.uuid4().hex[:12]
    # Extension: from the original filename, otherwise from the mime type
    ext = _storage_extension(orig_filename, mime)
    fname = entry_id + (ext or ".bin")
    _write_item(fname, raw)

    if not mime:
        mime = mimetypes.guess_type(orig_filename or fname)[0] or "application/octet-stream"
    is_image = mime.startswith("image/")
    entry = {
        "id": entry_id,
        "type": "image" if is_image else "file",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ts": time.time(),
        "file": fname,
        "filename": orig_filename or fname,
        "mime": mime,
        "size": len(raw),
        "preview": orig_filename or fname,
    }
    return _commit_entry(entry)


def _add_bundle(uploaded_files):
    """Store several uploaded files as one ordered clipboard-history entry."""
    if len(uploaded_files) == 1:
        return _add_binary(*uploaded_files[0])
    if len(uploaded_files) < 2:
        raise ValueError("a bundle needs at least two files")

    entry_id = uuid.uuid4().hex[:12]
    stored = []
    try:
        for index, (raw, orig_filename, mime) in enumerate(uploaded_files):
            filename = _clean_filename(orig_filename) or f"file-{index + 1}.bin"
            mime = _clean_mime(mime)
            if not mime:
                mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            internal = f"{entry_id}_{index + 1}{_storage_extension(filename, mime) or '.bin'}"
            _write_item(internal, raw)
            stored.append({
                "file": internal,
                "filename": filename,
                "mime": mime,
                "size": len(raw),
                "type": "image" if mime.startswith("image/") else "file",
            })
    except Exception:
        for item in stored:
            try:
                os.remove(os.path.join(_items_dir(), item["file"]))
            except OSError:
                pass
        raise

    names = ", ".join(item["filename"] for item in stored[:3])
    if len(stored) > 3:
        names += f", +{len(stored) - 3} more"
    entry = {
        "id": entry_id,
        "type": "bundle",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ts": time.time(),
        "file": None,
        "files": stored,
        "filename": None,
        "mime": "application/zip",
        "size": sum(item["size"] for item in stored),
        "preview": names[:240],
    }
    return _commit_entry(entry)


# ---------- Request data extraction ----------
_TEXT_MIMES = {"application/x-www-form-urlencoded"} | RTF_MIMES
_GENERIC_MIMES = {""}
_TEXT_FIELDS = ("text", "value", "content", "clipboard", "string")


def _json_as_text(data):
    """Preserve JSON strings and sensibly convert other JSON clipboard values."""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in _TEXT_FIELDS:
            if key in data:
                value = data[key]
                return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)


def _form_text():
    for key in _TEXT_FIELDS:
        if key in request.form:
            return request.form.get(key, "")
    if len(request.form) == 1:
        return next(iter(request.form.values()))
    return None


def _decode_text_bytes(raw, allow_legacy=False):
    """Decode text from iOS and browsers without altering line endings or Unicode."""
    rtf = decode_rtf_bytes(raw)
    if rtf is not None:
        return rtf
    charset = request.mimetype_params.get("charset")
    candidates = []
    if charset:
        candidates.append(charset)
    if raw.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        candidates.append("utf-32")
    elif raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        candidates.append("utf-16")
    candidates.extend(("utf-8-sig", "utf-8"))
    if allow_legacy:
        candidates.append("latin-1")
    for encoding in candidates:
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return None


def _looks_like_text(raw):
    text = _decode_text_bytes(raw)
    if text is None:
        return False
    return all(ch.isprintable() or ch in "\r\n\t" for ch in text)


def _decode_base64(value):
    """Accept standard, URL-safe and data-URL Base64, including missing padding."""
    if not isinstance(value, str):
        return None, None
    encoded = value.strip()
    data_mime = None
    if encoded.lower().startswith("data:") and "," in encoded:
        header, encoded = encoded.split(",", 1)
        if ";base64" not in header.lower():
            return None, None
        data_mime = _clean_mime(header[5:].split(";", 1)[0])
    encoded = re.sub(r"\s+", "", encoded)
    encoded += "=" * (-len(encoded) % 4)
    try:
        return base64.b64decode(encoded, altchars=b"-_", validate=True), data_mime
    except (ValueError, base64.binascii.Error):
        return None, None


def _request_filename():
    """Read the filename variants commonly emitted by iOS Shortcuts and HTTP clients."""
    for parameter in ("filename", "file_name", "name"):
        value = request.args.get(parameter)
        if value:
            return _clean_filename(value)

    for header in ("X-Filename", "X-File-Name", "X-Clipboard-Filename"):
        value = request.headers.get(header)
        if value:
            return _clean_filename(unquote(value, encoding="utf-8", errors="replace"))

    disposition = request.headers.get("Content-Disposition", "")
    match = re.search(r"filename\*\s*=\s*(?:\"([^\"]*)\"|([^;]*))", disposition, re.I)
    if match:
        value = (match.group(1) or match.group(2) or "").strip()
        charset, separator, encoded = value.partition("''")
        if separator:
            try:
                return _clean_filename(unquote(encoded, encoding=charset or "utf-8", errors="replace"))
            except LookupError:
                return _clean_filename(unquote(encoded, encoding="utf-8", errors="replace"))
    _kind, options = parse_options_header(disposition)
    if options.get("filename"):
        return _clean_filename(options["filename"])

    _kind, options = parse_options_header(request.headers.get("Content-Type", ""))
    return _clean_filename(options.get("name"))


def _get_posted_text():
    """Accept JSON, common form fields or raw UTF text."""
    if request.is_json:
        return _json_as_text(request.get_json())
    form_value = _form_text()
    if form_value is not None:
        return form_value
    raw = request.get_data(cache=False)
    return _decode_text_bytes(raw, allow_legacy=True) or ""


def _extract_upload():
    """
    Extract (bytes, filename, mime) from:
      - multipart/form-data (any file field)
      - JSON {filename, data(base64), mime}
      - raw binary body (any Content-Type and common filename headers)
    """
    if request.files:
        f = next(iter(request.files.values()))
        return f.read(), _clean_filename(f.filename), _clean_mime(f.mimetype)

    if request.is_json:
        filename = _request_filename()
        if filename:
            return request.get_data(cache=True), filename, _clean_mime(request.content_type)
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or "data" not in data:
            return None, None, None
        raw, data_mime = _decode_base64(data.get("data"))
        if raw is None:
            return None, None, None
        return raw, _clean_filename(data.get("filename")), _clean_mime(data.get("mime")) or data_mime

    raw = request.get_data(cache=False)
    filename = _request_filename()
    if raw or filename is not None:
        return raw, filename, _clean_mime(request.content_type)
    return None, None, None


def _extract_multipart_uploads():
    """Read every uploaded multipart file, preserving the browser/client order."""
    uploaded = []
    for field in request.files:
        for storage in request.files.getlist(field):
            uploaded.append((
                storage.read(),
                _clean_filename(storage.filename),
                _clean_mime(storage.mimetype),
            ))
    return uploaded


def _uploads_from_zip(raw):
    """Read an iOS transport archive without extracting paths onto the filesystem."""
    if not raw:
        raise ValueError("empty archive")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = [
                info for info in archive.infolist()
                if not info.is_dir()
                and not info.filename.replace("\\", "/").startswith("__MACOSX/")
                and not info.filename.replace("\\", "/").endswith("/.DS_Store")
                and not info.filename.replace("\\", "/").endswith(".DS_Store")
            ]
            if not members:
                raise ValueError("archive contains no files")
            if len(members) > 500:
                raise ValueError("archive contains too many files")
            max_bytes = int(app.config["MAX_CONTENT_LENGTH"])
            if sum(info.file_size for info in members) > max_bytes:
                raise ValueError("expanded archive exceeds the upload limit")
            uploads = []
            expanded = 0
            for info in members:
                if info.flag_bits & 0x1:
                    raise ValueError("encrypted archives are not supported")
                filename = _clean_filename(info.filename) or "file.bin"
                chunks = []
                with archive.open(info) as source:
                    while True:
                        chunk = source.read(min(1024 * 1024, max_bytes - expanded + 1))
                        if not chunk:
                            break
                        expanded += len(chunk)
                        if expanded > max_bytes:
                            raise ValueError("expanded archive exceeds the upload limit")
                        chunks.append(chunk)
                uploads.append((
                    b"".join(chunks),
                    filename,
                    mimetypes.guess_type(filename)[0] or "application/octet-stream",
                ))
            return uploads
    except zipfile.BadZipFile as exc:
        raise ValueError("invalid ZIP archive") from exc


def _unique_zip_name(filename, used):
    filename = _clean_filename(filename) or "file.bin"
    stem, ext = os.path.splitext(filename)
    candidate = filename
    counter = 2
    while candidate.casefold() in used:
        candidate = f"{stem} ({counter}){ext}"
        counter += 1
    used.add(candidate.casefold())
    return candidate


def _bundle_zip(entry):
    output = io.BytesIO()
    used = set()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in entry.get("files", []):
            archive.write(
                os.path.join(_items_dir(), item["file"]),
                _unique_zip_name(item.get("filename"), used),
            )
    output.seek(0)
    return output


def _bundle_filename(entry):
    stamp = (entry.get("timestamp") or "").replace(":", "-")[:19]
    return f"clipboard-files-{stamp or entry['id']}.zip"


def _raw_item_response(entry):
    """Return an item in the form most useful to iOS Shortcuts and desktop clients."""
    if entry["type"] == "text":
        response = Response(_read_text(entry), content_type="text/plain; charset=utf-8")
    elif entry["type"] == "bundle":
        filename = _bundle_filename(entry)
        response = send_file(
            _bundle_zip(entry),
            mimetype="application/zip",
            download_name=filename,
            as_attachment=True,
        )
        response.headers["X-Clipboard-Filename"] = quote(filename, safe="")
        response.headers["X-Clipboard-File-Count"] = str(len(entry.get("files", [])))
    else:
        response = send_file(
            os.path.join(_items_dir(), entry["file"]),
            mimetype=entry["mime"] or "application/octet-stream",
            download_name=entry["filename"],
            as_attachment=entry["type"] == "file",
        )
        response.headers["X-Clipboard-Filename"] = quote(entry["filename"] or "", safe="")
    response.headers["X-Clipboard-Id"] = entry["id"]
    response.headers["X-Clipboard-Type"] = entry["type"]
    return response


def _bundle_member_response(entry, member_index):
    files = entry.get("files", [])
    if entry.get("type") != "bundle" or member_index < 0 or member_index >= len(files):
        return jsonify({"error": "not found"}), 404
    member = files[member_index]
    response = send_file(
        os.path.join(_items_dir(), member["file"]),
        mimetype=member.get("mime") or "application/octet-stream",
        download_name=member.get("filename") or "file.bin",
        as_attachment=member.get("type", "file") == "file",
    )
    response.headers["X-Clipboard-Filename"] = quote(member.get("filename") or "file.bin", safe="")
    response.headers["X-Clipboard-Id"] = entry["id"]
    response.headers["X-Clipboard-Type"] = member.get("type", "file")
    response.headers["X-Clipboard-Bundle-Index"] = str(member_index)
    return response


# ---------- Authentication & account selection ----------
# General/shared space: optional CLIPBOARD_TOKEN (API) and CLIPBOARD_PASSWORD (web page).
# Extra accounts (CLIPBOARD_ACCOUNTS): selected per request with ?user=NAME&password=PASS
# (handy at the end of a Shortcut URL), X-Clipboard-User / X-Clipboard-Password headers,
# or the web login. Each account is isolated.
@app.before_request
def _check_auth():
    p = request.path
    if p in ("/health", "/login", "/logout", "/setup"):
        return
    web = (p == "/" or p.startswith("/ui/"))

    # 1) Explicit account in the URL: ?user=NAME&password=PASS  (Shortcuts / Windows client)
    u = request.headers.get("X-Clipboard-User") or request.args.get("user")
    if u:
        supplied_password = request.headers.get("X-Clipboard-Password")
        if supplied_password is None:
            supplied_password = request.args.get("password", "")
        if u in ACCOUNTS and _same_secret(ACCOUNTS[u], supplied_password):
            _use_account(u)
            if web:  # remember it so the browser stays on this account
                session.permanent = True
                session["acct"] = u
            return
        if web:
            return redirect("/login?lang=" + _ui_lang())
        return jsonify({"error": "unauthorized"}), 401

    # 2) Web session already logged into an account
    if session.get("acct") in ACCOUNTS:
        _use_account(session["acct"])
        return

    # 3) General / shared space
    _use_general()
    if web:
        if WEB_PASSWORD and not session.get("auth"):
            token = request.args.get("token", "")
            if not (AUTH_TOKEN and _same_secret(AUTH_TOKEN, token)):
                return redirect("/login?lang=" + _ui_lang())
        return
    if AUTH_TOKEN:
        token = request.headers.get("X-Auth-Token") or request.args.get("token", "")
        if _same_secret(AUTH_TOKEN, token) or session.get("auth"):
            return
        return jsonify({"error": "unauthorized"}), 401
    return  # general space open (no token configured)


@app.after_request
def _set_response_headers(response):
    """Avoid caching clipboard data and add browser-safe defaults for local HTTP."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.errorhandler(BadRequest)
def _bad_request(_error):
    return jsonify({"error": "invalid request or JSON body"}), 400


@app.errorhandler(HistoryStoreError)
def _history_unavailable(error):
    # Log only the failure category, never account names, paths or clipboard data.
    app.logger.error("Clipboard history unavailable: %s", error.reason)
    return jsonify({"error": str(error), "code": "history_unavailable"}), 503, {"Retry-After": "5"}


@app.errorhandler(AccountStorageError)
def _account_storage_unavailable(error):
    app.logger.error("Clipboard account storage unavailable: %s", error.reason)
    code = "account_storage_conflict" if error.reason == "alias" else "account_storage_unavailable"
    return jsonify({"error": str(error), "code": code}), 503


@app.errorhandler(RequestEntityTooLarge)
def _upload_too_large(_error):
    return jsonify({
        "error": "request too large",
        "max_upload_mb": MAX_UPLOAD_MB,
    }), 413


LOGIN_HTML = """<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer"><meta name="color-scheme" content="light dark">
<title>Clipboard Bridge</title>{theme_init}<style>{css}</style></head>
<body><main class="login-wrap"><div class="login-panel">
<header class="head"><div class="brand">{logo}<h1>Clipboard Bridge</h1></div>{settings_button}</header>
{settings_panel}
<form method="post" action="/login?lang={lang}">
{err}{user_field}
<input type="password" name="password" placeholder="{password}" aria-label="{password}" autocomplete="current-password"{pw_autofocus}>
<button class="btn" type="submit">{login_label}</button>
</form></div></main><script>{js}</script></body></html>"""


@app.route("/login", methods=["GET", "POST"])
def login():
    lang = _ui_lang()
    strings = WEB_STRINGS[lang]
    destination = "/?lang=" + lang
    if not (WEB_PASSWORD or ACCOUNTS):
        return redirect(destination)
    err = ""
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        pw = request.form.get("password", "")
        if u:
            if u in ACCOUNTS and _same_secret(ACCOUNTS[u], pw):
                session.permanent = True
                session["acct"] = u
                session.pop("auth", None)
                return redirect(destination)
        elif not WEB_PASSWORD:               # shared space is open, no password
            session.clear()
            session.permanent = True
            session["lang"] = lang
            return redirect(destination)
        elif _same_secret(WEB_PASSWORD, pw):  # shared space password
            session.permanent = True
            session["auth"] = True
            session.pop("acct", None)
            return redirect(destination)
        err = f'<div class="err">{strings["login_error"]}</div>'
    user_field = (f'<input name="username" placeholder="{strings["username"]}" aria-label="{strings["username"]}" autocomplete="username" autofocus>'
                  if ACCOUNTS else '')
    pw_autofocus = '' if ACCOUNTS else ' autofocus'
    return Response(LOGIN_HTML.format(err=err, user_field=user_field, pw_autofocus=pw_autofocus,
                                     theme_init=_THEME_INIT, css=_HOME_CSS, logo=LOGO_SVG,
                                     settings_button=_settings_button(lang), js=_HOME_JS,
                                     settings_panel=_preferences_panel(lang, "/login"), lang=lang,
                                     password=strings["password"], login_label=strings["login"]),
                    mimetype="text/html")


@app.route("/logout")
def logout():
    lang = _ui_lang()
    session.clear()
    session.permanent = True
    session["lang"] = lang
    return redirect("/login" if (WEB_PASSWORD or ACCOUNTS) else "/")


# ---------- TEXT ----------
@app.route("/clipboard/text", methods=["GET", "POST"])
def clipboard_text():
    if request.method == "POST":
        entry = _add_text(_get_posted_text())
        return jsonify({"status": "ok", "id": entry["id"]})
    # GET -> latest text (compatible with the old client)
    e = _latest_of(("text",))
    return jsonify({"text": _read_text(e) if e else ""})


@app.route("/clipboard/text/raw", methods=["GET"])
def clipboard_text_raw():
    """Plain text (text/plain): handy for pasting into Shortcuts."""
    e = _latest_of(("text",))
    return _raw_item_response(e) if e else Response("", content_type="text/plain; charset=utf-8")


# ---------- IMAGES ----------
@app.route("/clipboard/image", methods=["POST"])
def push_image():
    raw, filename, mime = _extract_upload()
    if raw is None:
        return jsonify({"error": "no image data"}), 400
    if not mime:
        mime = "image/png"
    if not filename:
        filename = "clipboard" + (mimetypes.guess_extension(mime) or ".png")
    entry = _add_binary(raw, filename, mime)
    return jsonify({"status": "ok", "id": entry["id"], "filename": entry["filename"]})


@app.route("/clipboard/image/latest", methods=["GET"])
def image_latest():
    e = _latest_of(("image",))
    if not e:
        return jsonify({"error": "no images"}), 404
    with open(os.path.join(_items_dir(), e["file"]), "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return jsonify({"filename": e["filename"], "data": b64, "mime": e["mime"], "id": e["id"]})


@app.route("/clipboard/image/latest/raw", methods=["GET"])
def image_latest_raw():
    """Image as binary: Shortcuts receive it directly as a photo."""
    e = _latest_of(("image",))
    if not e:
        return jsonify({"error": "no images"}), 404
    return _raw_item_response(e)


# ---------- GENERIC FILES ----------
@app.route("/clipboard/file", methods=["POST"])
def push_file():
    """Accept a file as JSON Base64, multipart form data, or a raw HTTP body."""
    if request.files:
        uploads = _extract_multipart_uploads()
        if not uploads:
            return jsonify({"error": "file data missing or invalid"}), 400
        entry = _add_bundle(uploads)
        return jsonify({
            "status": "ok",
            "saved": entry.get("filename") or entry.get("preview"),
            "id": entry["id"],
            "type": entry["type"],
            "file_count": len(entry.get("files", [])) or 1,
        })
    raw, filename, mime = _extract_upload()
    if raw is None:
        return jsonify({"error": "file data missing or invalid"}), 400
    filename = filename or ("clipboard" + (mimetypes.guess_extension(mime or "") or ".bin"))
    entry = _add_binary(raw, filename, mime)
    return jsonify({"status": "ok", "saved": entry["filename"], "id": entry["id"]})


@app.route("/clipboard/file/latest", methods=["GET"])
def file_latest():
    e = _latest_of(("image", "file", "bundle"))
    if not e:
        return jsonify({"error": "no files"}), 404
    if e["type"] == "bundle":
        raw = _bundle_zip(e).getvalue()
        return jsonify({
            "filename": _bundle_filename(e),
            "data": base64.b64encode(raw).decode(),
            "mime": "application/zip",
            "id": e["id"],
            "type": "bundle",
            "file_count": len(e.get("files", [])),
            "files": _public_bundle_files(e),
        })
    with open(os.path.join(_items_dir(), e["file"]), "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return jsonify({
        "filename": e["filename"],
        "data": b64,
        "mime": e["mime"],
        "id": e["id"],
        "type": e["type"],
    })


# ---------- UNIVERSAL / HISTORY ----------
@app.route("/clipboard/latest", methods=["GET"])
def latest_any():
    """Latest item of any type, content included."""
    with _lock:
        index = _load_index()
        if not index:
            return jsonify({"type": "empty"})
        return jsonify(_entry_with_content(index[0]))


@app.route("/clipboard/latest/meta", methods=["GET"])
def latest_meta():
    """Latest metadata only, used by iOS before choosing how to restore a group."""
    index = _load_index()
    return jsonify(_meta(index[0]) if index else {"type": "empty"})


@app.route("/clipboard/latest/raw", methods=["GET"])
def latest_raw():
    """Latest item (any type) as raw content: text or binary file."""
    with _lock:
        index = _load_index()
        if not index:
            return Response("", content_type="text/plain; charset=utf-8")
        return _raw_item_response(index[0])


@app.route("/clipboard/raw", methods=["GET"])
def shortcut_latest_raw_legacy():
    """Compatibility alias used by the original published iPhone Shortcut."""
    return latest_raw()


@app.route("/clipboard", methods=["POST"])
@app.route("/1", methods=["POST"])
def push_any():
    """Single endpoint: store whatever arrives (text or binary) with no distinction.
    Made for a single iPhone Shortcut that sends the clipboard whatever its type."""
    if request.is_json:
        filename = _request_filename()
        if filename:
            e = _add_binary(request.get_data(cache=True), filename, _clean_mime(request.content_type))
            return jsonify({"status": "ok", "id": e["id"], "type": e["type"]})
        d = request.get_json()
        if isinstance(d, dict) and "data" in d:
            raw, fn, mime = _extract_upload()
            if raw is None:
                return jsonify({"error": "file data missing or invalid"}), 400
            fn = fn or ("clipboard" + (mimetypes.guess_extension(mime or "") or ".bin"))
            e = _add_binary(raw, fn, mime)
            return jsonify({"status": "ok", "id": e["id"], "type": e["type"]})
        e = _add_text(_json_as_text(d))
        return jsonify({"status": "ok", "id": e["id"], "type": "text"})

    if request.files:
        uploads = _extract_multipart_uploads()
        if not uploads:
            return jsonify({"error": "no data"}), 400
        e = _add_bundle(uploads)
        return jsonify({
            "status": "ok",
            "id": e["id"],
            "type": e["type"],
            "file_count": len(e.get("files", [])) or 1,
        })

    form_value = _form_text()
    if form_value is not None:
        e = _add_text(form_value)
        return jsonify({"status": "ok", "id": e["id"], "type": "text"})

    raw = request.get_data(cache=False)
    ctype = _clean_mime(request.content_type) or ""
    filename = _request_filename()
    explicit_text = ctype.startswith("text/") or ctype in _TEXT_MIMES
    generic_text = filename is None and ctype in _GENERIC_MIMES and raw and _looks_like_text(raw)
    if filename is None and (explicit_text or generic_text):
        text = _decode_text_bytes(raw, allow_legacy=explicit_text)
        if text is not None:
            e = _add_text(text)
            return jsonify({"status": "ok", "id": e["id"], "type": "text"})
    if not raw and filename is None:
        return jsonify({"error": "no data"}), 400
    filename = filename or ("clipboard" + (mimetypes.guess_extension(ctype) or ".bin"))
    e = _add_binary(raw, filename, ctype or None)
    return jsonify({"status": "ok", "id": e["id"], "type": e["type"]})


@app.route("/clipboard/bundle", methods=["POST"])
def push_bundle_archive():
    """Accept the ZIP transport produced by the iPhone multi-file Shortcut."""
    raw, _filename, _mime = _extract_upload()
    try:
        uploads = _uploads_from_zip(raw)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    entry = _add_bundle(uploads)
    return jsonify({
        "status": "ok",
        "id": entry["id"],
        "type": entry["type"],
        "file_count": len(entry.get("files", [])) or 1,
    })


@app.route("/clipboard/history", methods=["GET", "DELETE"])
def history():
    if request.method == "DELETE":
        with _lock:
            index = _load_index()
            _save_index([])
            for e in index:
                _delete_entry_files(e)
        return jsonify({"status": "cleared"})

    try:
        with _lock:
            page = _history_page(_load_index(), request.args)
            page["items"] = [_meta(e) for e in page["items"]]
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(page)


@app.route("/clipboard/item/<item_id>", methods=["GET", "DELETE"])
def item(item_id):
    with _lock:
        e = next((x for x in _load_index() if x["id"] == item_id), None)
        if not e:
            return jsonify({"error": "not found"}), 404
        if request.method == "DELETE":
            index = [x for x in _load_index() if x["id"] != item_id]
            _save_index(index)
            _delete_entry_files(e)
            return jsonify({"status": "deleted"})
        return jsonify(_entry_with_content(e))


@app.route("/clipboard/item/<item_id>/raw", methods=["GET"])
def item_raw(item_id):
    with _lock:
        e = next((x for x in _load_index() if x["id"] == item_id), None)
        if not e:
            return jsonify({"error": "not found"}), 404
        return _raw_item_response(e)


@app.route("/clipboard/item/<item_id>/file/<int:member_index>/raw", methods=["GET"])
def item_bundle_file_raw(item_id, member_index):
    with _lock:
        e = next((x for x in _load_index() if x["id"] == item_id), None)
        if not e:
            return jsonify({"error": "not found"}), 404
        return _bundle_member_response(e, member_index)


# ---------- Diagnostics ----------
@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "version": SERVER_VERSION,
        "items": len(_load_index()),
        "auth": bool(AUTH_TOKEN or WEB_PASSWORD or ACCOUNTS),
    })


# Inline logo and icons (SVG): no external images, works offline.
LOGO_SVG = ('<svg class="logo" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">'
            '<rect x="8" y="7" width="32" height="38" rx="6" fill="#263242"/>'
            '<rect x="12" y="13" width="24" height="27" rx="3.5" fill="#f5f7fa"/>'
            '<rect x="15" y="7" width="18" height="8" rx="3" fill="#96a0ac"/>'
            '<rect x="19" y="3" width="10" height="9" rx="3" fill="#606a78"/>'
            '<path d="M16 20h15l2 2-2 2H16l-2-2 2-2z" fill="#2d7df6"/>'
            '<rect x="16" y="27" width="16" height="2.5" rx="1.25" fill="#b0bac6"/>'
            '<rect x="16" y="33" width="16" height="2.5" rx="1.25" fill="#b0bac6"/></svg>')

# Lucide 1.57.0: original geometry, bundled inline for offline use.
# https://github.com/lucide-icons/lucide/tree/1.57.0
# ISC License
#
# Copyright (c) 2026 Lucide Icons and Contributors
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#
# ---
#
# The following Lucide icons are derived from the Feather project:
#
# airplay, alert-circle, alert-octagon, alert-triangle, aperture, arrow-down-circle, arrow-down-left, arrow-down-right, arrow-down, arrow-left-circle, arrow-left, arrow-right-circle, arrow-right, arrow-up-circle, arrow-up-left, arrow-up-right, arrow-up, at-sign, calendar, cast, check, chevron-down, chevron-left, chevron-right, chevron-up, chevrons-down, chevrons-left, chevrons-right, chevrons-up, circle, clipboard, clock, code, columns, command, compass, corner-down-left, corner-down-right, corner-left-down, corner-left-up, corner-right-down, corner-right-up, corner-up-left, corner-up-right, crosshair, database, divide-circle, divide-square, dollar-sign, download, external-link, feather, frown, hash, headphones, help-circle, info, italic, key, layout, life-buoy, link-2, link, loader, lock, log-in, log-out, maximize, meh, minimize, minimize-2, minus-circle, minus-square, minus, monitor, moon, more-horizontal, more-vertical, move, music, navigation-2, navigation, octagon, pause-circle, percent, plus-circle, plus-square, plus, power, radio, rss, search, server, share, shopping-bag, sidebar, smartphone, smile, square, table-2, tablet, target, terminal, trash-2, trash, triangle, tv, type, upload, x-circle, x-octagon, x-square, x, zoom-in, zoom-out
#
# The MIT License (MIT) (for the icons listed above)
#
# Copyright (c) 2013-present Cole Bemis
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
_S = ('xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
      'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
      'stroke-linecap="round" stroke-linejoin="round" class="ui-icon" '
      'aria-hidden="true" focusable="false"')
IC_TEXT = f'<svg {_S} data-icon="file-text"><path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" /><path d="M14 2v5a1 1 0 0 0 1 1h5" /><path d="M10 9H8" /><path d="M16 13H8" /><path d="M16 17H8" /></svg>'
IC_FILE = f'<svg {_S} data-icon="file"><path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" /><path d="M14 2v5a1 1 0 0 0 1 1h5" /></svg>'
IC_UP = f'<svg {_S} data-icon="upload"><path d="M12 3v12" /><path d="m17 8-5-5-5 5" /><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /></svg>'
IC_HIST = f'<svg {_S} data-icon="history"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" /><path d="M12 7v5l4 2" /></svg>'
IC_PHONE = f'<svg {_S} data-icon="smartphone"><rect width="14" height="20" x="5" y="2" rx="2" ry="2" /><path d="M12 18h.01" /></svg>'
IC_REFRESH = f'<svg {_S} data-icon="refresh-cw"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" /><path d="M8 16H3v5" /></svg>'
IC_TRASH = f'<svg {_S} data-icon="trash-2"><path d="M10 11v6" /><path d="M14 11v6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" /><path d="M3 6h18" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>'
IC_SETTINGS = f'<svg {_S} data-icon="settings"><path d="M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 0 3.319 1.915 2.34 2.34 0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 2.34 0 0 0-3.319 1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 2.34 0 0 1 6.35 6.051a2.34 2.34 0 0 0 3.319-1.915" /><circle cx="12" cy="12" r="3" /></svg>'
IC_SUN = f'<svg {_S} data-icon="sun"><circle cx="12" cy="12" r="4" /><path d="M12 2v2" /><path d="M12 20v2" /><path d="m4.93 4.93 1.41 1.41" /><path d="m17.66 17.66 1.41 1.41" /><path d="M2 12h2" /><path d="M20 12h2" /><path d="m6.34 17.66-1.41 1.41" /><path d="m19.07 4.93-1.41 1.41" /></svg>'
IC_MOON = f'<svg {_S} data-icon="moon"><path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401" /></svg>'
IC_SYSTEM = f'<svg {_S} data-icon="monitor"><rect width="20" height="14" x="2" y="3" rx="2" /><line x1="8" x2="16" y1="21" y2="21" /><line x1="12" x2="12" y1="17" y2="21" /></svg>'
IC_LINK = f'<svg {_S} data-icon="link"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" /></svg>'
IC_HEART = f'<svg {_S} data-icon="heart"><path d="M2 9.5a5.5 5.5 0 0 1 9.591-3.676.56.56 0 0 0 .818 0A5.49 5.49 0 0 1 22 9.5c0 2.29-1.5 4-3 5.5l-5.492 5.313a2 2 0 0 1-3 .019L5 15c-1.5-1.5-3-3.2-3-5.5" /></svg>'

_HOME_CSS = """
:root{color-scheme:light;--bg:#f7f8fa;--surface:#fff;--field:#f0f2f5;--hover:#e8ecf2;
--ink:#20242c;--muted:#606b7a;--line:#dce1e8;--accent:#2367d1;--accent-hover:#1b55b0;
--tint:#eaf1ff;--good:#16734c;--good-bg:#e9f6ee;--warning:#815513;--warning-bg:#fff6e4;
--danger:#b82a43;--danger-bg:#fff0f3}
:root[data-theme=dark]{color-scheme:dark;--bg:#17181b;--surface:#202226;--field:#24272d;
--hover:#30343c;--ink:#f0f2f6;--muted:#a9b2c0;--line:#373c45;--accent:#8ab6ff;
--accent-hover:#aacbff;--tint:#26344c;--good:#8bdbb0;--good-bg:#20372b;
--warning:#f0cd8a;--warning-bg:#342c1e;--danger:#ff9eac;--danger-bg:#38232b}
*{box-sizing:border-box}[hidden]{display:none!important}html{scroll-behavior:smooth;scroll-padding-top:20px}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
button,input,select,textarea{font:inherit;letter-spacing:0}button,a,summary{touch-action:manipulation;-webkit-tap-highlight-color:transparent}
a{color:var(--accent);text-underline-offset:3px}:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.ui-icon{display:block;width:18px;height:18px;aspect-ratio:1;flex:0 0 auto}
.wrap{width:100%;max-width:1000px;margin:auto;padding:28px 32px 40px}
.head{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:16px;padding-bottom:20px}
.brand{display:flex;align-items:center;gap:12px;min-width:0}.brand-copy{min-width:0}
.logo{width:40px;height:40px;flex:0 0 auto}.head h1{font-size:22px;line-height:1.25;margin:0;font-weight:650;overflow-wrap:normal}
.head p{margin:5px 0 0;font-size:12px;color:var(--muted);display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.active-space{min-width:0;overflow-wrap:anywhere}.online{color:var(--good);display:inline-flex;align-items:center;gap:6px}
.online::before{content:"";width:6px;height:6px;background:currentColor;border-radius:50%;flex-shrink:0}
.project-nav{border-block:1px solid var(--line);padding:10px 0;margin-bottom:22px;display:flex;align-items:center;gap:12px;justify-content:space-between}
.repo-link{display:inline-flex;align-items:center;gap:8px;color:var(--ink);font-size:13px;font-weight:600;text-decoration:none;min-height:44px;overflow-wrap:anywhere}
.repo-link svg{width:18px;height:18px;flex:0 0 auto;color:var(--accent)}.repo-link:hover{text-decoration:underline}
.support-link{display:inline-flex;align-items:center;justify-content:center;flex:0 0 44px;width:44px;height:44px;color:var(--danger);
border:1px solid transparent;background:var(--danger-bg);border-radius:6px;text-decoration:none;font-size:24px}
.support-link:hover{border-color:var(--danger)}
.support-link .ui-icon{width:21px;height:21px}
.web-settings{padding:18px 0 22px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin-bottom:22px}
.web-settings h2{margin:0 0 16px;font-size:16px;font-weight:650}
.preferences{display:grid;grid-template-columns:minmax(0,220px) minmax(0,1fr);gap:24px;align-items:start}
.language-form,.theme-form{min-width:0;margin:0;padding:0;border:0}
.field-label,.theme-form legend{display:block;font-size:13px;font-weight:600;margin-bottom:8px;padding:0;color:var(--ink)}
.language-form label{display:block}.language-form select{width:100%;min-height:46px}
select,input[type=search],input[readonly]{min-width:0;max-width:100%;background:var(--surface);color:var(--ink);
border:1px solid var(--line);border-radius:6px;padding:10px 12px;min-height:44px;font-size:14px}
.theme-options{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}
.theme-option{position:relative;min-width:0;cursor:pointer}
.theme-option input{position:absolute;width:1px;height:1px;opacity:0;inset:0;pointer-events:none}
.theme-option>span{display:flex;align-items:center;justify-content:center;gap:8px;background:var(--surface);border:1px solid var(--line);
border-radius:6px;min-height:46px;padding:8px;font-size:13px;font-weight:500;text-align:center;overflow-wrap:anywhere}
.theme-option svg{width:18px;height:18px;flex:0 0 auto}.theme-option:hover>span{background:var(--hover)}
.theme-option input:checked+span{background:var(--tint);border-color:var(--accent);color:var(--accent)}
.theme-option input:focus-visible+span{outline:2px solid var(--accent);outline-offset:3px}
.lang{display:flex;gap:12px;align-items:center;flex-wrap:wrap;overflow-wrap:anywhere;padding-top:18px;font-size:13px}
.lang .on{font-weight:600}.lang a{min-height:40px;display:inline-flex;align-items:center}
.composer{padding-bottom:24px;border-bottom:1px solid var(--line);margin-bottom:28px}
.composer-tabs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:280px;max-width:100%;gap:4px;padding:4px;background:var(--field);border-radius:8px;margin-bottom:16px}
.composer-tabs button{display:flex;align-items:center;justify-content:center;gap:8px;min-width:0;min-height:40px;padding:8px 12px;
border:1px solid transparent;border-radius:5px;background:transparent;color:var(--muted);font-size:14px;font-weight:600;cursor:pointer}
.composer-tabs button svg{width:18px;height:18px;flex:0 0 auto}
.composer-tabs button[aria-selected=true]{background:var(--surface);color:var(--ink);border-color:var(--line)}
.composer-tabs button:hover{color:var(--ink)}
.panel{min-width:0}.panel h2{font-size:16px;margin:0 0 12px}
textarea{display:block;width:100%;min-height:124px;resize:vertical;background:var(--surface);color:var(--ink);
border:1px solid var(--line);border-radius:8px;padding:14px;line-height:1.6;font-size:16px}
textarea::placeholder,input::placeholder{color:var(--muted);opacity:1}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:12px}
.btn{min-height:44px;display:inline-flex;justify-content:center;align-items:center;gap:8px;background:var(--accent);color:#fff;
border:1px solid transparent;border-radius:6px;font-size:13px;font-weight:600;padding:10px 14px;text-decoration:none;cursor:pointer;max-width:100%;overflow-wrap:anywhere}
[data-theme=dark] .btn{color:#11203b}.btn:hover{background:var(--accent-hover)}
.btn.ghost{background:var(--surface);color:var(--ink);border-color:var(--line)}.btn.ghost:hover{background:var(--hover)}
.btn.small{padding:8px 12px;min-height:40px;font-size:12px}.btn.danger{color:var(--danger)}
.btn svg{width:18px;height:18px;flex-shrink:0}.btn.icon-button{width:44px;height:44px;padding:10px;flex:0 0 44px}
.drop{min-height:124px;width:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;
border:1px dashed var(--line);border-radius:8px;background:var(--surface);color:var(--muted);cursor:pointer;padding:18px;font-size:14px}
.drop svg{width:26px;height:26px;color:var(--accent);margin-bottom:6px}.drop b{color:var(--ink);font-weight:600}
.drop:hover,.drop.hover{background:var(--tint);border-color:var(--accent)}
.history{margin-bottom:28px}.history-title{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:12px;margin-bottom:16px}
.history-title h2{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:17px;margin:0;font-weight:650}
.count{font-size:12px;font-weight:500;color:var(--muted);background:var(--field);padding:2px 8px;border-radius:5px}
.history-tools{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.history-filter{display:grid;grid-template-columns:minmax(0,1fr) minmax(120px,180px) auto;gap:8px;margin-bottom:18px}
.history-filter input[type=search]{width:100%}.history-filter select{width:100%}
.history-list{border-top:1px solid var(--line)}
.item{display:grid;grid-template-columns:40px minmax(0,1fr) auto;align-items:center;column-gap:12px;row-gap:10px;padding:16px 0;border-bottom:1px solid var(--line);min-width:0}
.thumb,.ico{width:40px;height:40px;border-radius:6px;background:var(--tint);border:1px solid var(--line)}
.thumb{object-fit:cover}.ico{display:flex;align-items:center;justify-content:center;color:var(--accent)}.ico svg{width:20px;height:20px}
.meta{min-width:0}.prev{font-size:14px;overflow-wrap:anywhere;font-weight:500;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden}
.sub{font-size:12px;color:var(--muted);margin-top:5px;display:flex;column-gap:10px;row-gap:2px;flex-wrap:wrap;overflow-wrap:anywhere}
.actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end;min-width:0}.empty{color:var(--muted);padding:28px 10px;text-align:center}
.pagination{justify-content:flex-end;color:var(--muted);font-size:12px}.pagination>span{margin-right:auto}
.setup-guide{margin-bottom:24px}.setup-guide>summary{font-size:18px}.setup-page .setup-guide>summary{display:none}
summary{cursor:pointer;color:var(--ink);font-weight:600;padding:12px 0}summary::marker{color:var(--muted)}
.setup-guide p,.setup-section li,.shortcut-content>p{color:var(--muted)}.setup-content{padding-top:0}
.setup-intro{display:grid;grid-template-columns:minmax(0,1fr) 140px;gap:24px;margin:0 0 20px}
.setup-address{min-width:0}.setup-address>p{margin-top:6px}.qr{margin:0;text-align:center}
.qr svg{width:124px;height:124px;display:block;margin:auto;background:#fff;border:8px solid #fff;border-radius:6px}
.qr figcaption{font-size:12px;color:var(--muted);margin-top:8px}.setup-section{border-top:1px solid var(--line);padding:4px 0}
.setup-section summary{font-size:15px}.setup-section ol{padding-left:22px;max-width:800px}.setup-section li{padding-left:4px;margin:12px 0}
.resource-links{display:flex;gap:10px 18px;flex-wrap:wrap;margin:12px 0}.resource-link{font-size:13px;overflow-wrap:anywhere;display:inline-flex;align-items:center;min-height:32px}
.url{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:10px;padding:8px 10px;background:var(--field);
border:1px solid var(--line);border-radius:6px;margin:8px 0 16px}
.url code{min-width:0;white-space:normal;overflow-wrap:anywhere;font-size:12px;background:none;padding:0;color:var(--ink)}
.method{color:var(--accent);font-size:11px;font-weight:700}
code{font-size:12px;background:var(--tint);color:var(--ink);border-radius:4px;padding:2px 5px;overflow-wrap:anywhere}
.nota{color:var(--warning);background:var(--warning-bg);border-radius:6px;padding:12px;margin:12px 0;font-size:13px}
.shortcut-content{padding:8px 0}.shortcut-content h3{font-size:13px;margin-bottom:6px}
.foot{border-top:1px solid var(--line);padding-top:18px;font-size:12px;color:var(--muted)}.foot .resource-links{margin:6px 0}
.support-note{max-width:680px;margin-bottom:0}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);max-width:calc(100% - 32px);background:var(--ink);
color:var(--surface);padding:10px 18px;border-radius:6px;opacity:0;transition:opacity .15s;pointer-events:none;z-index:10}
.toast.show{opacity:1}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.login-wrap{display:flex;align-items:center;justify-content:center;min-height:100dvh;padding:24px}
.login-panel{width:420px;max-width:100%;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:24px}
.login-panel .head{padding-bottom:16px}.login-panel .head h1{font-size:20px}.login-panel .logo{width:32px;height:32px}
.login-panel .web-settings{padding-top:16px}.login-panel .preferences{grid-template-columns:minmax(0,1fr);gap:16px}
.login-panel .theme-option>span{flex-direction:column}
.login-panel input:not([type=radio]){width:100%;background:var(--field);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:12px;margin:0 0 12px;font-size:16px}
.login-panel button[type=submit]{width:100%}.err{color:var(--danger);font-size:13px;margin-bottom:12px}
.setup-page{max-width:900px}.setup-page>h2{font-size:20px;line-height:1.35;margin:22px 0 16px}
@media(max-width:600px){.wrap{padding:20px 16px 28px}.head{gap:12px;padding-bottom:16px}.head h1{font-size:20px}.logo{width:36px;height:36px}.brand{gap:10px}
.preferences{grid-template-columns:minmax(0,1fr);gap:18px}.theme-option>span{flex-direction:column;min-height:64px;padding:10px 6px;gap:6px}
.project-nav{margin-bottom:20px;gap:10px}.composer-tabs{width:100%}.composer-tabs button{min-height:44px}
.composer{padding-bottom:22px;margin-bottom:24px}.composer .row .btn{flex:1;min-width:0}
.history-filter{grid-template-columns:minmax(0,1fr) auto}.history-filter input[type=search]{grid-column:1/-1;font-size:16px}
.history-title{gap:8px}.history-title h2{font-size:16px}.history-tools{gap:6px}.history-tools .btn{min-height:44px}
.item{grid-template-columns:36px minmax(0,1fr);gap:10px}.thumb,.ico{width:36px;height:36px}.actions{grid-column:2;justify-content:flex-start}
.actions .btn{min-height:44px}.setup-intro{grid-template-columns:minmax(0,1fr)}.qr{display:flex;align-items:center;gap:16px;text-align:left}
.qr svg{width:90px;height:90px;margin:0}.qr>div{flex:0 0 90px}.qr figcaption{max-width:240px}
.url{grid-template-columns:auto minmax(0,1fr);gap:8px}.url .btn{grid-column:2;justify-self:start}.url code{line-height:1.6}
}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*::before,*::after{transition:none!important}}
"""

_THEME_INIT = """<script>
(function(){
var preference='system';
try{var stored=localStorage.getItem('clipboard-bridge-theme');if(['system','light','dark'].includes(stored))preference=stored;}catch(e){}
var media=window.matchMedia('(prefers-color-scheme: dark)');
function apply(){document.documentElement.dataset.theme=preference==='system'?(media.matches?'dark':'light'):preference;}
window.setBridgeTheme=function(value){if(!['system','light','dark'].includes(value))return;preference=value;try{localStorage.setItem('clipboard-bridge-theme',value);}catch(e){}apply();};
window.bridgeThemePreference=function(){return preference;};
if(media.addEventListener)media.addEventListener('change',function(){if(preference==='system')apply();});
apply();
})();
</script>"""


_HOME_JS = """
function toast(m){var t=document.getElementById('toast');t.textContent=m;t.classList.add('show');
clearTimeout(window._t);window._t=setTimeout(function(){t.classList.remove('show');},1400);}
function copyText(s){var a=document.createElement('textarea');a.value=s;a.style.position='fixed';
a.style.opacity='0';document.body.appendChild(a);a.focus();a.select();
try{document.execCommand('copy');}catch(e){}document.body.removeChild(a);toast(T_COPIED);}
function deleteItem(id){if(!confirm(T_DEL))return;
fetch('/clipboard/item/'+id+TOKENQS,{method:'DELETE'}).then(checkResult).catch(function(){toast(T_ERROR);});}
function clearHistory(){if(!confirm(T_CLEAR))return;
fetch('/clipboard/history'+TOKENQS,{method:'DELETE'}).then(checkResult).catch(function(){toast(T_ERROR);});}
function checkResult(r){if(!r.ok)throw new Error('Request failed');location.reload();}
document.querySelectorAll('[data-theme-selector]').forEach(function(radio){
radio.checked=radio.value===window.bridgeThemePreference();
radio.addEventListener('change',function(){if(this.checked)window.setBridgeTheme(this.value);});});
document.querySelectorAll('[data-settings-toggle]').forEach(function(button){
button.addEventListener('click',function(){var panel=document.getElementById('web-settings');
panel.hidden=!panel.hidden;button.setAttribute('aria-expanded',String(!panel.hidden));});});
(function(){var tabs=Array.from(document.querySelectorAll('[data-compose-tab]'));if(!tabs.length)return;
function activate(tab,focus){tabs.forEach(function(other){var selected=other===tab;
other.setAttribute('aria-selected',String(selected));other.tabIndex=selected?0:-1;
document.getElementById(other.getAttribute('aria-controls')).hidden=!selected;});
if(focus)tab.focus();}
tabs.forEach(function(tab,index){tab.addEventListener('click',function(){activate(tab,false);});
tab.addEventListener('keydown',function(e){var next;
if(e.key==='ArrowRight')next=(index+1)%tabs.length;
else if(e.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;
else if(e.key==='Home')next=0;else if(e.key==='End')next=tabs.length-1;
if(next!==undefined){e.preventDefault();activate(tabs[next],true);}});});
activate(tabs[0],false);})();
(function(){var z=document.getElementById('drop'),f=document.getElementById('file'),
fm=document.getElementById('upform');if(!z)return;z.onclick=function(){f.click();};
function on(e){e.preventDefault();z.classList.add('hover');}
function off(e){e.preventDefault();z.classList.remove('hover');}
z.addEventListener('dragover',on);z.addEventListener('dragenter',on);z.addEventListener('dragleave',off);
z.addEventListener('drop',function(e){off(e);if(e.dataTransfer.files.length){f.files=e.dataTransfer.files;fm.submit();}});
f.addEventListener('change',function(){if(f.files.length)fm.submit();});})();
"""


def _human(n):
    n = float(n or 0)
    for u in ("B", "KB", "MB"):
        if n < 1024:
            return f"{int(n)} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} GB"


def _urlrow(method, url, copy_label):
    js_url = escape(json.dumps(url))
    return (f'<div class="url"><span class="method">{method}</span>'
            f'<code>{escape(url)}</code>'
            f'<button class="btn small ghost" type="button" '
            f'onclick="copyText({js_url})">{copy_label}</button></div>')


def _ui_token():
    return request.args.get("token", "")


def _ui_lang():
    requested = request.args.get("lang")
    lang = (requested if requested is not None else session.get("lang", "en"))
    lang = lang.lower().replace("_", "-").split("-", 1)[0]
    lang = lang if lang in WEB_LANGUAGES else "en"
    if requested is not None and session.get("lang") != lang:
        session.permanent = True
        session["lang"] = lang
    return lang


def _home_url():
    tok = _ui_token()
    return "/?lang=" + _ui_lang() + (("&token=" + quote(tok, safe="")) if tok else "")


with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_web_strings.json"),
          encoding="utf-8") as _translations:
    WEB_STRINGS = json.load(_translations)

WEB_LANGUAGES = {
    "en": "English", "it": "Italiano", "es": "Español", "fr": "Français",
    "de": "Deutsch", "pt": "Português", "zh": "简体中文",
}
PROJECT_SITE = "https://mattboxx.github.io/Clipboard-Bridge/"


def _language_selector(lang, action="/"):
    options = "".join(
        f'<option value="{code}"{" selected" if code == lang else ""}>{name}</option>'
        for code, name in WEB_LANGUAGES.items()
    )
    token = _ui_token()
    hidden = f'<input type="hidden" name="token" value="{escape(token)}">' if token else ""
    label = WEB_STRINGS[lang]["language"]
    return (f'<form class="language-form" method="get" action="{action}">{hidden}'
            f'<label><span class="field-label">{label}</span>'
            f'<select name="lang" aria-label="{label}" onchange="this.form.submit()">'
            f'{options}</select></label><noscript><button type="submit">{label}</button></noscript></form>')


def _public_link(url, label):
    return (f'<a class="resource-link" href="{escape(url)}" target="_blank" '
            f'rel="noopener noreferrer">{label}</a>')


def _theme_selector(lang):
    strings = WEB_STRINGS[lang]
    icons = {"system": IC_SYSTEM, "light": IC_SUN, "dark": IC_MOON}
    options = "".join(
        f'<label class="theme-option"><input type="radio" name="theme" value="{mode}" data-theme-selector>'
        f'<span>{icons[mode]}<span>{strings["theme_" + mode]}</span></span></label>'
        for mode in ("light", "dark", "system"))
    return (f'<fieldset class="theme-form"><legend>{strings["theme"]}</legend>'
            f'<div class="theme-options">{options}</div></fieldset>')


def _settings_button(lang):
    label = WEB_STRINGS[lang]["settings"]
    return (f'<button class="btn ghost icon-button" type="button" data-settings-toggle '
            f'aria-controls="web-settings" aria-expanded="false" aria-label="{label}" title="{label}">'
            f'{IC_SETTINGS}</button>')


def _preferences_panel(lang, action="/", account_bar=""):
    strings = WEB_STRINGS[lang]
    return (f'<section class="web-settings" id="web-settings" hidden aria-labelledby="settings-heading">'
            f'<h2 id="settings-heading">{strings["settings"]}</h2><div class="preferences">'
            f'{_language_selector(lang, action)}{_theme_selector(lang)}</div>{account_bar}</section>')


def _shortcut_endpoints(lang, base, suffix="", account=None, token=""):
    strings = WEB_STRINGS[lang]
    notice = f'<div class="nota">{strings["auth_optional"]}</div>'
    if account:
        notice += (f'<p>{strings["acct_note"].format(name=escape(account))}</p>'
                   '<p><code>X-Clipboard-User</code> &middot; <code>X-Clipboard-Password</code></p>')
    elif token:
        notice += f'<p>{strings["token_note"]} <code>X-Auth-Token</code></p>'
    return (f'<div class="shortcut-content">{notice}<p>{strings["iphone_intro"]}</p>'
            f'<h3>{strings["ip_send"]}</h3>{_urlrow("POST", base + "/clipboard" + suffix, strings["copy"])}'
            f'<h3>{strings["ip_recv"]}</h3>{_urlrow("GET", base + "/clipboard/latest/raw" + suffix, strings["copy"])}'
            f'<details><summary>{strings["ip_multi"]}</summary><h3>{strings["ip_bundle"]}</h3>'
            f'{_urlrow("POST", base + "/clipboard/bundle" + suffix, strings["copy"])}'
            f'<h3>{strings["ip_meta"]}</h3>{_urlrow("GET", base + "/clipboard/latest/meta" + suffix, strings["copy"])}</details></div>')


@lru_cache(maxsize=1)
def _download_qr():
    return qrcode.make(DOWNLOAD_URL, image_factory=SvgPathImage).to_string().decode("ascii")


def _connection_guide(lang, base, *, expanded=False, shortcut_details=""):
    strings = WEB_STRINGS[lang]
    tutorial = PROJECT_SITE + ("tutorial.it.html" if lang == "it" else "tutorial.html")
    guide_label = strings["platform_guide"] + (" (English)" if lang not in ("en", "it") else "")
    sections = ""
    for key, title, fragment in (
        ("apple", "iPhone, iPad &amp; Mac", "iphone"),
        ("windows", "Windows", "windows"), ("android", "Android", "android"),
        ("container", strings["container_title"], "docker"),
    ):
        steps = "".join(f'<li>{strings[f"{key}_{n}"]}</li>' for n in (1, 2, 3))
        opened = " open" if expanded and key == "apple" else ""
        extra = shortcut_details if key == "apple" else ""
        guide_url = (PROJECT_SITE + "#server" if key == "container" else tutorial + "#" + fragment)
        sections += (f'<details class="setup-section" id="guide-{key}"{opened}>'
                     f'<summary>{title}</summary><ol>{steps}</ol>{extra}'
                     f'{_public_link(guide_url, guide_label)}</details>')
    # This QR contains a public download URL, never pairing secrets or account data.
    qr = _download_qr()
    opened = " open" if expanded else ""
    return (f'<details class="setup-guide" id="connect"{opened}><summary>{strings["connect"]}</summary>'
            f'<div class="setup-content"><p>{strings["connect_intro"]}</p>'
            f'<div class="setup-intro"><div class="setup-address"><strong>{strings["server_address"]}</strong>'
            f'{_urlrow("URL", base, strings["copy"])}<p>{strings["network_tip"]}</p>'
            f'<p>{strings["account_tip"]}</p><div class="resource-links">'
            f'{_public_link(DOWNLOAD_URL, strings["downloads"])}'
            f'{_public_link(tutorial, strings["setup_guide"])}</div></div>'
            f'<figure class="qr"><div aria-hidden="true">{qr}</div><figcaption>{strings["qr_note"]}</figcaption>'
            f'</figure></div>{sections}</div></details>')

def render_home():
    tok = _ui_token()
    lang = _ui_lang()
    S = WEB_STRINGS[lang]
    encoded_token = quote(tok, safe="")
    tq = ("?token=" + encoded_token) if tok else ""             # token only (raw / API / img)
    fq = "?lang=" + lang + (("&token=" + encoded_token) if tok else "")  # forms / redirect
    acct = getattr(g, "account", None)                          # current account (or None = shared)

    e = _latest_of(("text",))
    latest_text = _read_text(e) if e else ""

    items = _load_index()
    search_query = request.args.get("q", "")
    type_filter = request.args.get("type", "")
    page = _history_page(items, {
        "q": search_query, "type": type_filter, "limit": "20",
        "offset": request.args.get("offset", "0"),
    })
    rows = ""
    for it in page["items"]:
        tid, kind = it["id"], it["type"]
        prev = escape(it.get("preview") or S["no_preview"])
        label = (f'{len(it.get("files", []))} {S["files"]}'
                 if kind == "bundle" else S[kind + "_type"])
        timestamp = it.get("timestamp") or ""
        try:
            stamp = datetime.fromisoformat(timestamp).strftime("%d/%m/%Y, %H:%M")
        except ValueError:
            stamp = timestamp
        sub = (f'<span>{label} &middot; {_human(it.get("size"))}</span>'
               f'<time datetime="{escape(timestamp)}">{escape(stamp)}</time>')
        if kind == "image":
            media = f'<img class="thumb" src="/clipboard/item/{tid}/raw{tq}" alt="">'
        else:
            media = f'<span class="ico">{IC_FILE if kind in ("file", "bundle") else IC_TEXT}</span>'
        rows += (f'<div class="item">{media}'
                 f'<div class="meta"><div class="prev">{prev}</div><div class="sub">{sub}</div></div>'
                 f'<div class="actions">'
                 f'<a class="btn small ghost" href="/clipboard/item/{tid}/raw{tq}">{S["download"]}</a>'
                 f"<button class=\"btn small ghost\" type=\"button\" onclick=\"deleteItem('{tid}')\">{S['delete']}</button>"
                 f'</div></div>')
    if not rows:
        rows = f'<div class="empty">{S["no_results"] if search_query or type_filter else S["empty"]}</div>'

    options = ''.join(
        f'<option value="{kind}"{" selected" if type_filter == kind else ""}>{S[label]}</option>'
        for kind, label in (("", "all_types"), ("text", "text_type"), ("image", "image_type"),
                            ("file", "file_type"), ("bundle", "bundle_type"))
    )
    navigation = f'<span>{S["results"].format(n=page["total"])}</span>'
    for offset, label, enabled in ((max(0, page["offset"] - 20), "previous", page["offset"] > 0),
                                   (page["offset"] + 20, "next", page["has_more"])):
        if enabled:
            params = {"lang": lang, "q": search_query, "type": type_filter, "offset": offset}
            if tok:
                params["token"] = tok
            navigation += f'<a class="btn small ghost" href="/?{escape(urlencode(params))}#history">{S[label]}</a>'

    tutorial = PROJECT_SITE + ("tutorial.it.html" if lang == "it" else "tutorial.html")
    guide_label = S["setup_guide"] + (" (English)" if lang not in ("en", "it") else "")

    # Current space + login/logout link
    if acct:
        account_bar = (f'<div class="lang"><span class="on">{escape(acct)}</span>'
                       f'<a href="/logout">{S["logout"]}</a></div>')
    elif session.get("auth"):
        account_bar = (f'<div class="lang"><span class="on">{S["shared"]}</span>'
                       f'<a href="/logout">{S["logout"]}</a></div>')
    elif ACCOUNTS or WEB_PASSWORD:
        account_bar = f'<div class="lang"><a href="/login">{S["login"]}</a></div>'
    else:
        account_bar = ""

    js_consts = (f"const TOKENQS={json.dumps(tq)};"
                 f"const T_COPIED={json.dumps(S['js_copied'])};"
                 f"const T_DEL={json.dumps(S['js_del'])};"
                 f"const T_ERROR={json.dumps(S['js_error'])};"
                 f"const T_CLEAR={json.dumps(S['js_clear'])};")

    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer"><meta name="color-scheme" content="light dark">
<title>Clipboard Bridge</title>{_THEME_INIT}<style>{_HOME_CSS}</style>
<noscript><style>#web-settings[hidden]{{display:block!important}}.composer-tabs,[data-settings-toggle]{{display:none}}</style></noscript></head>
<body><main class="wrap">
<header class="head"><div class="brand">{LOGO_SVG}<div class="brand-copy">
<h1>Clipboard Bridge</h1><p><span class="online">{S["status_online"]}</span>
<span class="active-space">{escape("@" + acct if acct else S["shared"])}</span></p></div></div>
{_settings_button(lang)}</header>
{_preferences_panel(lang, account_bar=account_bar)}

<nav class="project-nav" id="project-links" aria-label="{S['connect']}">
<a class="repo-link" href="/setup?lang={lang}">{IC_LINK}{S["connect"]}</a>
<a class="support-link" href="https://ko-fi.com/mattboxx" target="_blank" rel="noopener noreferrer" title="{escape(S['support_note'])}" aria-label="{S['support']}">{IC_HEART}<span class="sr-only">{S["support"]}</span></a>
</nav>

<section class="composer" aria-label="{S['subtitle']}">
<div class="composer-tabs" role="tablist" aria-label="{S['all_types']}">
<button id="text-tab" type="button" role="tab" data-compose-tab aria-selected="true" aria-controls="text-panel">{IC_TEXT}{S["h_text"]}</button>
<button id="file-tab" type="button" role="tab" data-compose-tab aria-selected="false" aria-controls="file-panel" tabindex="-1">{IC_FILE}{S["h_file"]}</button>
</div>
<div class="panel" id="text-panel" role="tabpanel" aria-labelledby="text-tab">
<form method="post" action="/ui/text{fq}">
<textarea id="txt" name="text" aria-label="{S["h_text"]}" placeholder="{S["ph_text"]}">{escape(latest_text)}</textarea>
<div class="row"><button class="btn" type="submit">{IC_UP}{S["save"]}</button>
<button class="btn ghost" type="button" onclick="copyText(document.getElementById('txt').value)">{S["copy"]}</button></div>
</form></div>
<div class="panel" id="file-panel" role="tabpanel" aria-labelledby="file-tab">
<form id="upform" method="post" action="/ui/upload{fq}" enctype="multipart/form-data">
<button class="drop" id="drop" type="button" aria-label="{S['upload']}">{IC_UP}<b>{S["drop2"]}</b><span>{S["drop1"]}</span></button>
<input id="file" type="file" name="file" multiple hidden>
<noscript><style>#file[hidden]{{display:block!important}}</style><button class="btn" type="submit">{S["upload"]}</button></noscript>
</form></div>
</section>

<section class="history" id="history" aria-labelledby="history-heading">
<div class="history-title"><h2 id="history-heading">{S["h_history"]}<span class="count">{len(items)}</span></h2>
<div class="history-tools"><button class="btn ghost icon-button" type="button" onclick="location.reload()" aria-label="{S['refresh']}" title="{S['refresh']}">{IC_REFRESH}</button>
<button class="btn ghost danger" type="button" onclick="clearHistory()">{S["clear"]}</button></div></div>
<form method="get" action="/#history" class="history-filter">
<input type="hidden" name="lang" value="{lang}">
{('<input type="hidden" name="token" value="' + str(escape(tok)) + '">') if tok else ''}
<input type="search" name="q" value="{escape(search_query)}" placeholder="{S['search']}" aria-label="{S['search']}" maxlength="200">
<select name="type" aria-label="{S['all_types']}">{options}</select>
<button class="btn ghost" type="submit">{S['search_button']}</button>
</form>
<div class="history-list">{rows}</div>
<nav class="row pagination" aria-label="{S['h_history']}">{navigation}</nav>
</section>

<footer class="foot"><span>{S["foot"]}</span><div class="resource-links">
<a class="repo-link" href="https://github.com/Mattboxx/Clipboard-Bridge" target="_blank" rel="noopener noreferrer">GitHub</a>
{_public_link(PROJECT_SITE, S["project_site"])}{_public_link(tutorial, guide_label)}</div><p class="support-note">{S["support_note"]}</p></footer>
</main><div id="toast" class="toast" role="status" aria-live="polite"></div>
<script>{js_consts}{_HOME_JS}</script>
</body></html>"""
@app.route("/")
def home():
    try:
        with _lock:
            content = render_home()
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return Response(content, mimetype="text/html")


@app.get("/setup")
def setup():
    lang = _ui_lang()
    strings = WEB_STRINGS[lang]
    try:
        address = PUBLIC_ADDRESS or base_address(request.host_url)
    except ValueError:
        return Response("Invalid server address", status=400)
    # Public setup deliberately does not read the active account or expose its data.
    guide = _connection_guide(lang, address, expanded=True,
                              shortcut_details=_shortcut_endpoints(lang, address))
    html = f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer"><meta name="color-scheme" content="light dark">
<title>{strings["connect"]} | Clipboard Bridge</title>{_THEME_INIT}<style>{_HOME_CSS}</style></head>
<body><main class="wrap setup-page"><header class="head"><div class="brand">{LOGO_SVG}
<div class="brand-copy"><h1>Clipboard Bridge</h1></div></div>{_settings_button(lang)}</header>
{_preferences_panel(lang, "/setup")}
<nav class="project-nav"><a class="repo-link" href="/?lang={lang}">{strings["h_history"]}</a>
<a class="repo-link" href="{PROJECT_SITE}" target="_blank" rel="noopener noreferrer">{strings["project_site"]}</a></nav>
<h2>{strings["connect"]}</h2>{guide}</main><div id="toast" class="toast" role="status" aria-live="polite"></div>
<script>const T_COPIED={json.dumps(strings["js_copied"])};{_HOME_JS}</script></body></html>"""
    return Response(html, mimetype="text/html", headers={"Cache-Control": "no-store"})

@app.route("/ui/text", methods=["POST"])
def ui_text():
    _add_text(request.form.get("text", ""))
    return redirect(_home_url())


@app.route("/ui/upload", methods=["POST"])
def ui_upload():
    uploads = [
        (f.read(), f.filename, f.mimetype or None)
        for f in request.files.getlist("file")
        if f and f.filename
    ]
    if uploads:
        _add_bundle(uploads)
    return redirect(_home_url())


if __name__ == "__main__":
    print("=" * 52)
    print(" Clipboard Bridge - Server")
    print(f"   Listening on:   http://0.0.0.0:{PORT}")
    print(f"   Data folder:    {DATA_DIR}")
    print(f"   Max history:    {MAX_HISTORY} items")
    print(f"   Max upload:     {MAX_UPLOAD_MB} MB")
    print(f"   API token:      {'ON' if AUTH_TOKEN else 'disabled'}")
    print(f"   Web password:   {'ON' if WEB_PASSWORD else 'disabled'}")
    if ACCOUNTS:
        names = list(ACCOUNTS)
        shown = ", ".join(names[:10]) + (f", +{len(names) - 10} more" if len(names) > 10 else "")
        print(f"   Accounts:       {len(ACCOUNTS)} ({shown}) + shared")
    print("=" * 52)
    app.run(host="0.0.0.0", port=PORT)
