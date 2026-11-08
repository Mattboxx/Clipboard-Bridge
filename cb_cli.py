#!/usr/bin/env python3
"""cb-cli: send and receive Clipboard Bridge items from a terminal.

Uses only the Python standard library and the server's universal /clipboard API.

Configuration is read from the environment so credentials never appear in the
process list or shell history:

  CB_URL            Base address of the server, e.g. http://192.168.1.20:5088 (required;
                    --url overrides it)
  CB_TOKEN          Shared-space API token (sent as X-Auth-Token), or
  CB_TOKEN_FILE     a file holding the token (plain, or a CLIPBOARD_TOKEN=/API_TOKEN= line)
  CB_USER           Account name (selects an isolated account instead of the shared space)
  CB_PASSWORD       Account password, or
  CB_PASSWORD_FILE  a file holding the password

With none of the credential variables set, the shared space is used without
authentication (valid only if the server has no token configured).
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import quote, unquote, urlsplit

__version__ = "0.2.0"

TIMEOUT = 120
TOKEN_KEYS = ("CLIPBOARD_TOKEN", "API_TOKEN")


def die(msg: str, code: int = 1) -> NoReturn:
    print(f"cb-cli: {msg}", file=sys.stderr)
    raise SystemExit(code)


def decode_secret_file(raw: bytes) -> str:
    """Decode UTF-8 (with or without BOM) or the UTF-16 that Windows PowerShell's `>` writes."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        die("secret file is not valid UTF-8 or UTF-16 text")


def read_secret(file_path: str, keys: Sequence[str]) -> str:
    """Return the first line of a secret file, or the value of a KEY=value line."""
    try:
        raw = Path(file_path).expanduser().read_bytes()
    except OSError as exc:
        die(f"cannot read {file_path}: {exc.strerror}")
    lines = decode_secret_file(raw).splitlines()
    for line in lines:
        key, sep, value = line.partition("=")
        if sep and key.strip() in keys and value.strip():
            return value.strip().strip("'\"")
    first = lines[0].strip() if lines else ""
    if not first or "=" in first and first.partition("=")[0].strip().isupper():
        die(f"no secret found in {file_path}")
    return first


def env_secret(var: str, keys: Sequence[str]) -> str:
    value = os.environ.get(var, "")
    if value:
        return value
    file_path = os.environ.get(var + "_FILE", "")
    return read_secret(file_path, keys) if file_path else ""


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class Client:
    def __init__(self, url: str | None) -> None:
        base = (url or os.environ.get("CB_URL", "")).strip().rstrip("/")
        if not base:
            die("no server address: set CB_URL or pass --url (for example http://HOST_IP:5088)")
        try:
            parts = urlsplit(base)
            port = parts.port
        except ValueError:
            die("invalid server address")
        if (parts.scheme not in ("http", "https") or not parts.hostname
                or parts.username is not None or parts.query or parts.fragment
                or "?" in base or "#" in base or port == 0
                or any(ch.isspace() or ord(ch) < 32 for ch in base)):
            die("use an http:// or https:// server address without credentials, query or fragment")
        self.base = base
        self.opener = urllib.request.build_opener(NoRedirects())
        self.auth: dict[str, str] = {}
        user = os.environ.get("CB_USER", "")
        if user:
            password = env_secret("CB_PASSWORD", ())
            if not password:
                die("CB_USER requires CB_PASSWORD or CB_PASSWORD_FILE")
            self.auth = {"X-Clipboard-User": user, "X-Clipboard-Password": password}
        else:
            token = env_secret("CB_TOKEN", TOKEN_KEYS)
            if token:
                self.auth = {"X-Auth-Token": token}
        if any(any(not 32 <= ord(ch) <= 255 or ord(ch) == 127 for ch in value)
               for value in self.auth.values()):
            die("credentials contain characters not supported by HTTP headers")
        if self.auth and parts.scheme == "http" and not is_loopback(parts.hostname):
            print("cb-cli: warning: credentials are sent unencrypted over http; "
                  "use https or a trusted network", file=sys.stderr)

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        req = urllib.request.Request(
            self.base + path, data=body, method=method, headers={**self.auth, **(headers or {})}
        )
        try:
            with self.opener.open(req, timeout=TIMEOUT) as resp:
                return resp.read(), {k.lower(): v for k, v in resp.headers.items()}
        except urllib.error.HTTPError as exc:
            if 300 <= exc.code < 400:
                exc.close()
                die("server redirected the request; configure its final address")
            detail = ""
            try:
                detail = str(json.loads(exc.read(8192)).get("error", ""))
            except (ValueError, AttributeError):
                pass
            finally:
                exc.close()
            hint = " (check token or account credentials)" if exc.code == 401 else ""
            die(f"HTTP {exc.code}{hint}: {detail or exc.reason}")
        except urllib.error.URLError as exc:
            die(f"cannot reach {self.base}: {exc.reason}")
        except (OSError, ValueError) as exc:
            die(f"request failed: {exc}")


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def clipboard_text(data: bytes | None = None) -> bytes:
    """Read or write the desktop text clipboard without invoking a shell."""
    reading = data is None
    if os.environ.get("WAYLAND_DISPLAY") and os.environ.get("XDG_SESSION_TYPE") != "x11":
        tool = "wl-paste" if reading else "wl-copy"
        command = [tool, "--type", "text" if reading else "text/plain;charset=utf-8"]
        if reading:
            command.append("--no-newline")
        package = "wl-clipboard"
    elif os.environ.get("DISPLAY"):
        tool = package = "xclip"
        command = [tool, "-selection", "clipboard", "-target", "UTF8_STRING",
                   "-out" if reading else "-in"]
    else:
        die("no Wayland or X11 session; use stdin or --out instead")
    if not shutil.which(tool):
        die(f"{tool} is missing; install {package} for this desktop session")
    try:
        result = subprocess.run(
            command, input=data, stdout=subprocess.PIPE if reading else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=10, check=True,
        )
        return result.stdout if reading else b""
    except (OSError, subprocess.SubprocessError):
        die(f"{tool} could not {'read' if reading else 'write'} the text clipboard")


def looks_like_text(data: bytes) -> bool:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return b"\x00" not in data


def guess_mime(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def multipart(files: list[Path]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    out = bytearray()
    for i, path in enumerate(files):
        name = quote(path.name, safe="")
        out += f"--{boundary}\r\n".encode()
        out += (
            f'Content-Disposition: form-data; name="file{i}"; filename*=UTF-8\'\'{name}\r\n'
            f"Content-Type: {guess_mime(path.name)}\r\n\r\n"
        ).encode()
        out += path.read_bytes() + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def report_push(raw: bytes) -> None:
    info: dict[str, Any] = json.loads(raw)
    extra = f" ({info['file_count']} files)" if info.get("file_count", 1) > 1 else ""
    print(f"sent {info.get('type', '?')} {info.get('id', '')}{extra}", file=sys.stderr)


def cmd_push(c: Client, args: argparse.Namespace) -> None:
    if args.clipboard:
        if args.files or args.name or args.text is not None:
            die("--clipboard cannot be combined with --text, --name or file paths")
        data = clipboard_text()
        if not data or not looks_like_text(data):
            die("the desktop clipboard does not contain UTF-8 text")
        raw, _ = c.request("POST", "/clipboard", data, {"Content-Type": "text/plain; charset=utf-8"})
        report_push(raw)
        return
    if args.text is not None:
        raw, _ = c.request("POST", "/clipboard", args.text.encode(),
                           {"Content-Type": "text/plain; charset=utf-8"})
        report_push(raw)
        return
    if args.files:
        paths = [Path(f) for f in args.files]
        for p in paths:
            if not p.is_file():
                die(f"not a file: {p}")
        if len(paths) == 1:
            p = paths[0]
            raw, _ = c.request("POST", "/clipboard", p.read_bytes(), {
                "Content-Type": guess_mime(p.name),
                "X-Clipboard-Filename": quote(p.name, safe=""),
            })
        else:
            body, ctype = multipart(paths)
            raw, _ = c.request("POST", "/clipboard", body, {"Content-Type": ctype})
        report_push(raw)
        return
    if sys.stdin.isatty():
        die("nothing to send: give -t TEXT, FILE..., or pipe data on stdin")
    data = sys.stdin.buffer.read()
    if not data:
        die("stdin was empty")
    hdrs = {"Content-Type": "text/plain; charset=utf-8"}
    if args.name or not looks_like_text(data):
        name = args.name or "stdin.bin"
        hdrs = {"Content-Type": guess_mime(name), "X-Clipboard-Filename": quote(name, safe="")}
    raw, _ = c.request("POST", "/clipboard", data, hdrs)
    report_push(raw)


WINDOWS_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WINDOWS_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.IGNORECASE)


def is_windows() -> bool:
    return sys.platform == "win32"


def windows_safe_name(name: str) -> str:
    """Make a received file name valid on Windows (invalid characters, trailing dots, device names)."""
    name = WINDOWS_INVALID.sub("_", name).rstrip(" .")
    if not name:
        return "file"
    return "_" + name if WINDOWS_RESERVED.match(name) else name


def safe_name(header: str, fallback: str) -> str:
    # Split by hand: on Windows Path("a:b").name would treat "a:" as a drive and drop it.
    name = unquote(header).replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable())
    if is_windows():
        name = windows_safe_name(name)
    return name if name not in ("", ".", "..") else fallback


def cmd_pull(c: Client, args: argparse.Namespace) -> None:
    if args.clipboard and args.out:
        die("--clipboard cannot be combined with --out")
    path = f"/clipboard/item/{quote(args.id, safe='')}/raw" if args.id else "/clipboard/latest/raw"
    data, h = c.request("GET", path)
    kind = h.get("x-clipboard-type", "")
    if not kind and (not data or h.get("content-type", "").startswith("application/json")):
        die("clipboard is empty", 2)
    text = kind == "text" or (not kind and looks_like_text(data))
    if args.clipboard:
        if not text:
            die("the item is a file; use pull -o PATH to save it")
        clipboard_text(data)
        print("copied to the desktop clipboard", file=sys.stderr)
        return
    if text:
        if args.out and args.out != "-":
            save_file(Path(args.out), data, args.force)
        else:
            sys.stdout.buffer.write(data)
            if sys.stdout.isatty() and not data.endswith(b"\n"):
                sys.stdout.write("\n")
        return
    fname = safe_name(h.get("x-clipboard-filename", ""), "clipboard-item")
    if args.out == "-" or (args.out is None and not sys.stdout.isatty()):
        sys.stdout.buffer.write(data)
        return
    dest = Path(args.out) if args.out else Path(fname)
    if dest.is_dir():
        dest = dest / fname
    save_file(dest, data, args.force)
    print(f"saved {kind or 'file'} -> {dest} ({len(data)} bytes)", file=sys.stderr)


def save_file(dest: Path, data: bytes, force: bool) -> None:
    try:
        with dest.open("wb" if force else "xb") as output:
            output.write(data)
    except FileExistsError:
        die(f"{dest} exists (use -f to overwrite)")


def cmd_ls(c: Client, args: argparse.Namespace) -> None:
    raw, _ = c.request("GET", f"/clipboard/history?limit={args.n}")
    page: dict[str, Any] = json.loads(raw)
    if args.json:
        print(json.dumps(page, indent=2))
        return
    items = page.get("items", [])
    if not items:
        print("(empty)", file=sys.stderr)
        return
    print(f"{'ID':<12}  {'TIME':<19}  {'TYPE':<6} {'SIZE':>8}  NAME/PREVIEW")
    for it in items:
        label = it.get("filename") or (it.get("preview") or "")[:60]
        label = "".join(ch if ch.isprintable() else " " for ch in label)
        print(f"{it['id']:<12}  {str(it.get('timestamp', ''))[:19]:<19}  "
              f"{it['type']:<6} {it.get('size') or '':>8}  {label}")


def cmd_rm(c: Client, args: argparse.Namespace) -> None:
    if args.all:
        c.request("DELETE", "/clipboard/history")
        print("history cleared", file=sys.stderr)
    elif args.id:
        c.request("DELETE", f"/clipboard/item/{quote(args.id, safe='')}")
        print(f"deleted {args.id}", file=sys.stderr)
    else:
        die("give an ID or --all")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cb-cli",
        description="Send and receive Clipboard Bridge items (see the module docstring "
                    "or README for the CB_* environment variables).",
    )
    p.add_argument("--version", action="version", version=f"cb-cli {__version__}")
    p.add_argument("--url", help="server base address (default: $CB_URL)")
    sub = p.add_subparsers(dest="cmd", required=True)

    push = sub.add_parser("push", aliases=["send", "put"], help="send text (-t / stdin) or file(s)")
    push.add_argument("-t", "--text", help="literal text to send")
    push.add_argument("-n", "--name", help="filename when piping file data on stdin")
    push.add_argument("-c", "--clipboard", action="store_true", help="read text from the Linux clipboard")
    push.add_argument("files", nargs="*", help="one file, or several (sent as one bundle)")
    push.set_defaults(fn=cmd_push)

    pull = sub.add_parser("pull", aliases=["receive", "get"],
                          help="fetch the latest item (or ID); text goes to stdout")
    pull.add_argument("id", nargs="?", help="history ID (default: latest)")
    pull.add_argument("-o", "--out", help="write to PATH or directory ('-' = stdout)")
    pull.add_argument("-f", "--force", action="store_true", help="overwrite an existing file")
    pull.add_argument("-c", "--clipboard", action="store_true", help="copy received text to the Linux clipboard")
    pull.set_defaults(fn=cmd_pull)

    ls = sub.add_parser("ls", aliases=["list"], help="list history (newest first)")
    ls.add_argument("-n", type=int, default=20, help="maximum items (default 20)")
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(fn=cmd_ls)

    rm = sub.add_parser("rm", help="delete an item, or --all")
    rm.add_argument("id", nargs="?")
    rm.add_argument("--all", action="store_true")
    rm.set_defaults(fn=cmd_rm)
    return p


def make_output_safe() -> None:
    """Never fail on a clip preview the console encoding cannot represent."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass


def main(argv: Sequence[str] | None = None) -> None:
    make_output_safe()
    args = build_parser().parse_args(argv)
    try:
        args.fn(Client(args.url), args)
    except BrokenPipeError:
        raise
    except (OSError, ValueError) as exc:
        die(str(exc))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
