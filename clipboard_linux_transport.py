"""HTTP and desktop clipboard adapters for the Linux graphical client."""

import json
import mimetypes
import os
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from clipboard_setup import base_address


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Connection:
    def __init__(self, address, auth=None):
        self.base = base_address(address)
        self.auth = auth or {}
        if any(not value.isprintable() or any(ord(ch) > 255 for ch in value)
               for value in self.auth.values()):
            raise ValueError("The credentials contain unsupported HTTP header characters.")
        self.opener = build_opener(RejectRedirects())

    def request(self, method, path, data=None, headers=None):
        request = Request(self.base + path, data=data, method=method,
                          headers={**self.auth, **(headers or {})})
        try:
            with self.opener.open(request, timeout=20) as response:
                return response.read(), {key.lower(): value for key, value in response.headers.items()}
        except HTTPError as error:
            error.close()
            if 300 <= error.code < 400:
                message = "Server redirected the request. Enter its final address."
            elif error.code in (401, 403):
                message = "Access denied. Check the account or shared token in Connection settings."
            elif error.code == 413:
                message = "Upload exceeds the server limit."
            else:
                message = f"Server returned HTTP {error.code}."
            raise RuntimeError(message) from error
        except URLError as error:
            raise RuntimeError(f"Could not reach the server: {error.reason}") from error

    def history(self, limit, *, search="", kind=""):
        query = urlencode({"limit": limit, "q": search, "type": kind})
        content, _ = self.request("GET", "/clipboard/history?" + query)
        return json.loads(content)

    def item(self, item_id=None):
        resource = "/latest" if item_id is None else "/item/" + quote(item_id, safe="")
        return self.request("GET", "/clipboard" + resource + "/raw")

    def send_text(self, data):
        self.request("POST", "/clipboard", data, {"Content-Type": "text/plain; charset=utf-8"})

    def send_files(self, paths):
        boundary = uuid4().hex
        chunks = []
        for index, path in enumerate(paths):
            filename = quote(path.name, safe="")
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            chunks.append(
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"file{index}\"; filename*=UTF-8''{filename}\r\n"
                f"Content-Type: {mime}\r\n\r\n".encode("ascii")
            )
            chunks.extend((path.read_bytes(), b"\r\n"))
        chunks.append(f"--{boundary}--\r\n".encode("ascii"))
        self.request("POST", "/clipboard", b"".join(chunks),
                     {"Content-Type": f"multipart/form-data; boundary={boundary}"})


def clipboard_text(data=None):
    read = data is None
    if os.environ.get("WAYLAND_DISPLAY") and os.environ.get("XDG_SESSION_TYPE") != "x11":
        package = "wl-clipboard"
        command = (["wl-paste", "--no-newline", "--type", "text"] if read else
                   ["wl-copy", "--type", "text/plain;charset=utf-8"])
    elif os.environ.get("DISPLAY"):
        package = "xclip"
        command = ["xclip", "-selection", "clipboard", "-target", "UTF8_STRING",
                   "-out" if read else "-in"]
    else:
        raise RuntimeError("No Wayland or X11 session was found.")
    try:
        result = subprocess.run(command, input=data, check=True, timeout=10,
                                stdout=subprocess.PIPE if read else subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    except FileNotFoundError as error:
        raise RuntimeError(f"Install {package} to use the desktop clipboard.") from error
    except subprocess.SubprocessError as error:
        raise RuntimeError(f"Could not {'read' if read else 'write'} the desktop clipboard.") from error
    return result.stdout
