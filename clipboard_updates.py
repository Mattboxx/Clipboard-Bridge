"""GitHub release updates. No account credentials or clipboard data are used."""

import ctypes
from ctypes import wintypes
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


REPOSITORY = "Mattboxx/Clipboard-Bridge"
RELEASE_PAGE = f"https://github.com/{REPOSITORY}/releases/latest"
RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
MAX_DOWNLOAD = 256 * 1024 * 1024
API_LIMIT = 1024 * 1024
HELPER_FLAG = "--clipboard-bridge-apply-update"
DOWNLOAD_HOSTS = {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}


class UpdateError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,5}\.[0-9]{1,5}\.[0-9]{1,5}", value):
        raise UpdateError("invalid_release")
    values = tuple(map(int, value.split(".")))
    if any(part > 65535 for part in values):
        raise UpdateError("invalid_release")
    return values


def executable_architecture(path):
    try:
        with open(path, "rb") as source:
            if source.read(2) != b"MZ":
                raise UpdateError("unsupported_build")
            source.seek(0x3C)
            offset = struct.unpack("<I", source.read(4))[0]
            source.seek(offset)
            if source.read(4) != b"PE\0\0":
                raise UpdateError("unsupported_build")
            machine = struct.unpack("<H", source.read(2))[0]
        return {0x8664: "x64", 0xAA64: "arm64"}[machine]
    except (OSError, KeyError, struct.error):
        raise UpdateError("unsupported_build") from None


def file_digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _https(url, hosts):
    try:
        parsed = urllib.parse.urlsplit(url)
        valid = (parsed.scheme == "https" and parsed.hostname in hosts
                 and parsed.port in (None, 443) and not parsed.username and not parsed.password
                 and not parsed.fragment)
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise UpdateError("invalid_release")
    return url


class _Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = hosts

    def redirect_request(self, request, fp, code, message, headers, url):
        _https(url, self.hosts)
        return super().redirect_request(request, fp, code, message, headers, url)


def _open(url, *, metadata=False):
    hosts = {"api.github.com"} if metadata else DOWNLOAD_HOSTS
    _https(url, hosts)
    opener = urllib.request.build_opener(_Redirects(hosts))
    request = urllib.request.Request(url, headers={
        "User-Agent": "Clipboard-Bridge-Updater",
        "Accept": "application/vnd.github+json" if metadata else "application/octet-stream",
    })
    return opener.open(request, timeout=12 if metadata else 30)


@dataclass(frozen=True)
class Update:
    version: str
    architecture: str
    kind: str
    name: str
    url: str
    size: int
    sha256: str
    executable_sha256: str


def select_update(release, current, architecture, kind):
    if architecture not in ("x64", "arm64") or kind not in ("installer", "portable"):
        raise UpdateError("unsupported_build")
    current_parts = version_tuple(current)
    if not isinstance(release, dict) or release.get("draft") is not False or release.get("prerelease") is not False:
        raise UpdateError("invalid_release")
    version = release.get("tag_name")
    # Standalone-server and Android releases are never Windows update candidates.
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        return None
    if version_tuple(version) <= current_parts:
        return None
    assets = release.get("assets")
    if not isinstance(assets, list) or len(assets) > 200:
        raise UpdateError("invalid_release")
    portable = f"Clipboard.Bridge.Portable.Windows.{architecture}.V{version}.exe"
    wanted = portable if kind == "portable" else f"Clipboard.Bridge_windows_client_and_server_setup_{architecture}_V{version}.exe"

    def asset(name):
        matches = [item for item in assets if isinstance(item, dict) and item.get("name") == name]
        if len(matches) != 1:
            raise UpdateError("invalid_release")
        item = matches[0]
        url = f"https://github.com/{REPOSITORY}/releases/download/{version}/{name}"
        digest = item.get("digest", "")
        size = item.get("size")
        if (item.get("browser_download_url") != url or item.get("state") != "uploaded"
                or type(size) is not int or not 0 < size <= MAX_DOWNLOAD
                or not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)):
            raise UpdateError("invalid_release")
        return item, digest[7:]

    payload, checksum = asset(wanted)
    _, executable_checksum = asset(portable)
    return Update(version, architecture, kind, wanted, payload["browser_download_url"],
                  payload["size"], checksum, executable_checksum)


def check_update(current, architecture, kind, *, open_url=None):
    try:
        with (open_url or _open)(RELEASE_API, metadata=True) as response:
            raw = response.read(API_LIMIT + 1)
        if len(raw) > API_LIMIT:
            raise UpdateError("invalid_release")
        return select_update(json.loads(raw), current, architecture, kind)
    except UpdateError:
        raise
    except (ValueError, OSError, urllib.error.URLError):
        raise UpdateError("check_failed") from None


def mark_download(path, url):
    if os.name == "nt":
        # Keep Windows Internet-zone checks. Never remove Mark of the Web.
        with open(str(path) + ":Zone.Identifier", "w", encoding="ascii") as output:
            output.write("[ZoneTransfer]\nZoneId=3\nHostUrl=" + _https(url, {"github.com"}) + "\n")


def download_update(update, cache, *, progress=None, cancelled=None, open_url=None):
    folder = Path(cache) / uuid.uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    target = folder / update.name
    partial = target.with_suffix(".part")
    digest, count = hashlib.sha256(), 0
    try:
        with (open_url or _open)(update.url) as response, partial.open("xb") as output:
            while True:
                if cancelled is not None and cancelled.is_set():
                    raise UpdateError("cancelled")
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                count += len(chunk)
                if count > update.size or count > MAX_DOWNLOAD:
                    raise UpdateError("integrity_failed")
                output.write(chunk)
                digest.update(chunk)
                if progress:
                    progress(count, update.size)
            output.flush()
            os.fsync(output.fileno())
        if count != update.size or digest.hexdigest() != update.sha256:
            raise UpdateError("integrity_failed")
        mark_download(partial, update.url)
        os.replace(partial, target)
        return target
    except Exception as error:
        for owned in (partial, target):
            try:
                owned.unlink(missing_ok=True)
            except OSError:
                pass
        # The operation owns this new directory; never recursively remove a cache root.
        try:
            folder.rmdir()
        except OSError:
            pass
        if isinstance(error, UpdateError):
            raise
        raise UpdateError("download_failed") from None


def _write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=True)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def prune_finished_updates(cache, *, now=None):
    """Remove only recognized, finished update files older than seven days."""
    root = Path(cache).resolve()
    if not root.is_dir():
        return
    cutoff = (time.time() if now is None else now) - 7 * 86400
    try:
        folders = list(root.iterdir())
    except OSError:
        return
    for folder in folders:
        try:
            if (not re.fullmatch(r"[0-9a-f]{32}", folder.name) or folder.is_symlink()
                    or folder.resolve().parent != root or not folder.is_dir()):
                continue
            result = folder / "result.json"
            if not result.is_file() or result.stat().st_mtime >= cutoff:
                continue
            files = list(folder.iterdir())
            names = {"request.json", "ready.json", "cancel.json", "result.json", "runner.exe"}
            if any(path.is_symlink() or not path.is_file() or (path.name not in names and not re.fullmatch(
                    r"Clipboard\.Bridge(?:\.Portable\.Windows\.(?:x64|arm64)\.V|_windows_client_and_server_setup_(?:x64|arm64)_V)[0-9.]+\.exe",
                    path.name)) for path in files):
                continue
            for path in files:
                path.unlink()
            folder.rmdir()
        except OSError:
            continue


def file_version(path):
    version = ctypes.WinDLL("version", use_last_error=True)
    size = version.GetFileVersionInfoSizeW
    size.argtypes, size.restype = (wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)), wintypes.DWORD
    ignored = wintypes.DWORD()
    length = size(str(path), ctypes.byref(ignored))
    if not length or length > 1024 * 1024:
        raise UpdateError("integrity_failed")
    buffer = ctypes.create_string_buffer(length)
    get = version.GetFileVersionInfoW
    get.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p)
    get.restype = wintypes.BOOL
    query = version.VerQueryValueW
    query.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT))
    query.restype = wintypes.BOOL
    pointer, count = ctypes.c_void_p(), wintypes.UINT()
    if not get(str(path), 0, length, buffer) or not query(buffer, "\\", ctypes.byref(pointer), ctypes.byref(count)):
        raise UpdateError("integrity_failed")
    if count.value < 52:
        raise UpdateError("integrity_failed")
    fields = struct.unpack("13I", ctypes.string_at(pointer, 52))
    if fields[0] != 0xFEEF04BD:
        raise UpdateError("integrity_failed")
    return fields[2] >> 16, fields[2] & 65535, fields[3] >> 16


def verify_executable(path, checksum, version, architecture=None):
    if (file_digest(path) != checksum or (architecture is not None and executable_architecture(path) != architecture)
            or file_version(path) != version_tuple(version)):
        raise UpdateError("integrity_failed")


def prepare_handoff(update, payload, executable, cache, *, parent_pid=None, language="en"):
    payload, executable, cache = Path(payload).resolve(), Path(executable).resolve(), Path(cache).resolve()
    if payload.parent.parent != cache or not re.fullmatch(r"[0-9a-f]{32}", payload.parent.name):
        raise UpdateError("invalid_ticket")
    if payload.name != update.name or file_digest(payload) != update.sha256:
        raise UpdateError("integrity_failed")
    verify_executable(payload, update.sha256, update.version, update.architecture
                      if update.kind == "portable" else None)
    if not executable.is_file() or executable.suffix.lower() != ".exe":
        raise UpdateError("unsupported_build")
    # Preflight writes before asking the app to quit, including read-only portable folders.
    probe = executable.parent / (".clipboard-update-" + uuid.uuid4().hex)
    try:
        with probe.open("xb"):
            pass
    except OSError:
        raise UpdateError("folder_readonly") from None
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
    if any((payload.parent / name).exists() for name in ("request.json", "ready.json", "cancel.json", "result.json")):
        # A timed-out helper may still be waiting for its original parent. Never
        # recycle its ticket or remove its cancellation marker during a retry.
        folder = cache / uuid.uuid4().hex
        folder.mkdir(exist_ok=False)
        fresh = folder / update.name
        shutil.copy2(payload, fresh)
        verify_executable(fresh, update.sha256, update.version, update.architecture
                          if update.kind == "portable" else None)
        payload = fresh
    runner = payload.parent / "runner.exe"
    shutil.copy2(executable, runner)
    ticket = payload.parent / "request.json"
    _write_json(ticket, {"schema": 1, "update": asdict(update), "target": str(executable),
                         "original_sha256": file_digest(executable),
                         "parent_pid": parent_pid or os.getpid(), "language": "it" if language == "it" else "en"})
    return ticket


def launch_handoff(ticket, *, timeout=30):
    ticket = Path(ticket)
    process = subprocess.Popen([str(ticket.parent / "runner.exe"), HELPER_FLAG, str(ticket)],
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if (ticket.parent / "ready.json").is_file():
            return process
        if process.poll() is not None:
            raise UpdateError("handoff_failed")
        time.sleep(.1)
    _write_json(ticket.parent / "cancel.json", {"cancelled": True})
    raise UpdateError("handoff_failed")


def _process_handle(pid, expected_image):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes, kernel.OpenProcess.restype = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD), wintypes.HANDLE
    handle = kernel.OpenProcess(0x100000 | 0x1000, False, pid)
    if not handle:
        raise UpdateError("handoff_failed")
    query = kernel.QueryFullProcessImageNameW
    query.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    query.restype = wintypes.BOOL
    name, size = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
    if not query(handle, 0, name, ctypes.byref(size)) or Path(name.value).resolve() != expected_image:
        _close_handle(handle)
        raise UpdateError("invalid_ticket")
    return handle


def _close_handle(handle):
    close = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
    close.argtypes, close.restype = (wintypes.HANDLE,), wintypes.BOOL
    close(handle)


def _wait(handle, milliseconds):
    wait = ctypes.WinDLL("kernel32", use_last_error=True).WaitForSingleObject
    wait.argtypes, wait.restype = (wintypes.HANDLE, wintypes.DWORD), wintypes.DWORD
    return wait(handle, milliseconds)


def _shell_open(path, arguments=(), *, wait=False, startup=False):
    if getattr(sys, "frozen", False):
        # This runs only in the helper, never in the UI. External installers must
        # not inherit PyInstaller's bundled-DLL search path or temporary runtime.
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.SetDllDirectoryW.argtypes, kernel.SetDllDirectoryW.restype = (wintypes.LPCWSTR,), wintypes.BOOL
        if not kernel.SetDllDirectoryW(None):
            raise UpdateError("launch_denied")
        os.environ["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        bundled = Path(sys._MEIPASS).resolve()
        entries = os.environ.get("PATH", "").split(os.pathsep)
        os.environ["PATH"] = os.pathsep.join(entry for entry in entries
            if entry and not Path(entry).resolve().is_relative_to(bundled))
    class ExecuteInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                    ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                    ("dwHotKey", wintypes.DWORD), ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]
    execute = ctypes.WinDLL("shell32", use_last_error=True).ShellExecuteExW
    execute.argtypes, execute.restype = (ctypes.POINTER(ExecuteInfo),), wintypes.BOOL
    info = ExecuteInfo()
    info.cbSize, info.fMask, info.lpVerb, info.nShow = ctypes.sizeof(info), 0x40 | 0x100, "open", 1
    info.lpFile, info.lpDirectory = str(path), str(Path(path).parent)
    info.lpParameters = subprocess.list2cmdline(list(arguments))
    ole = ctypes.OleDLL("ole32")
    ole.CoInitializeEx.argtypes, ole.CoInitializeEx.restype = (ctypes.c_void_p, wintypes.DWORD), ctypes.c_long
    initialized = ole.CoInitializeEx(None, 2 | 4) in (0, 1)
    try:
        if not execute(ctypes.byref(info)) or not info.hProcess:
            raise UpdateError("launch_denied")
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetProcessId.argtypes, kernel.GetProcessId.restype = (wintypes.HANDLE,), wintypes.DWORD
        pid = kernel.GetProcessId(info.hProcess)
        if wait:
            if _wait(info.hProcess, 0xFFFFFFFF) != 0:
                raise UpdateError("install_failed")
            code = wintypes.DWORD()
            kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
            kernel.GetExitCodeProcess.restype = wintypes.BOOL
            if not kernel.GetExitCodeProcess(info.hProcess, ctypes.byref(code)) or code.value not in (0, 3010):
                raise UpdateError("install_failed")
        elif startup and _wait(info.hProcess, 3000) == 0:
            code = wintypes.DWORD()
            kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
            kernel.GetExitCodeProcess.restype = wintypes.BOOL
            if not kernel.GetExitCodeProcess(info.hProcess, ctypes.byref(code)) or code.value:
                raise UpdateError("launch_denied")
        return pid
    finally:
        if info.hProcess:
            _close_handle(info.hProcess)
        if initialized:
            ole.CoUninitialize()


def _replace(source, target, timeout=30):
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise UpdateError("file_locked") from None
            time.sleep(.2)


def apply_ticket(ticket, cache):
    """Run in a copied frozen executable, never in the tray or UI process."""
    ticket, cache = Path(ticket).resolve(), Path(cache).resolve()
    if (ticket.name != "request.json" or ticket.parent.parent != cache
            or not re.fullmatch(r"[0-9a-f]{32}", ticket.parent.name)):
        return 1
    parent_handle = None
    target = backup = stage = None
    stopped = False
    installer_started = False
    phase = "ticket"
    try:
        if ticket.stat().st_size > 65536:
            raise UpdateError("invalid_ticket")
        with ticket.open(encoding="utf-8") as source:
            value = json.load(source)
        update = Update(**value["update"])
        # Revalidate the on-disk ticket, not only the original API response.
        def metadata(name, checksum):
            return {"name": name, "size": update.size, "digest": "sha256:" + checksum,
                    "state": "uploaded", "browser_download_url":
                    f"https://github.com/{REPOSITORY}/releases/download/{update.version}/{name}"}
        portable = f"Clipboard.Bridge.Portable.Windows.{update.architecture}.V{update.version}.exe"
        assets = [metadata(update.name, update.sha256)]
        if update.kind == "installer":
            assets.append(metadata(portable, update.executable_sha256))
        checked = select_update({"tag_name": update.version, "draft": False, "prerelease": False,
                                 "assets": assets}, "0.0.0", update.architecture, update.kind)
        if checked != update or type(value.get("original_sha256")) is not str or not re.fullmatch(
                r"[0-9a-f]{64}", value["original_sha256"]):
            raise UpdateError("invalid_ticket")
        target = Path(value["target"]).resolve(strict=True)
        payload = ticket.parent / update.name
        if (value.get("schema") != 1 or update.kind not in ("installer", "portable")
                or type(value.get("parent_pid")) is not int or value["parent_pid"] <= 0
                or payload.parent != ticket.parent or target.suffix.lower() != ".exe"
                or file_digest(target) != value["original_sha256"]):
            raise UpdateError("invalid_ticket")
        phase = "payload"
        verify_executable(payload, update.sha256, update.version, update.architecture
                          if update.kind == "portable" else None)
        phase = "parent"
        parent_handle = _process_handle(value["parent_pid"], target)
        phase = "ready"
        _write_json(ticket.parent / "ready.json", {"state": "ready"})
        if _wait(parent_handle, 120000) != 0:
            raise UpdateError("parent_timeout")
        if (ticket.parent / "cancel.json").exists():
            raise UpdateError("cancelled")
        stopped = True
        phase = "replace"
        if not target.is_file() or file_digest(target) != value["original_sha256"]:
            stopped = False  # Do not launch or overwrite an externally changed executable.
            raise UpdateError("target_changed")
        verify_executable(payload, update.sha256, update.version, update.architecture
                          if update.kind == "portable" else None)
        if update.kind == "installer":
            installer_started = True
            _shell_open(payload, ("/SP-", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/NOCLOSEAPPLICATIONS",
                                  "/NORESTARTAPPLICATIONS", "/RESTARTEXITCODE=3010",
                                  "/DIR=" + str(target.parent),
                                  "/LANG=" + ("italian" if value.get("language") == "it" else "english")), wait=True)
            verify_executable(target, update.executable_sha256, update.version, update.architecture)
        else:
            stage = target.parent / (".clipboard-update-" + ticket.parent.name + ".exe")
            backup = target.parent / (".clipboard-previous-" + ticket.parent.name + ".exe")
            if stage.exists() or backup.exists():
                raise UpdateError("invalid_ticket")
            shutil.copy2(payload, stage)
            verify_executable(stage, update.sha256, update.version, update.architecture)
            mark_download(stage, update.url)
            _replace(target, backup)
            _replace(stage, target)
        phase = "restart"
        pid = _shell_open(target, startup=True)
        _write_json(ticket.parent / "result.json", {"state": "installed", "version": update.version, "pid": pid})
        if backup:
            try:
                backup.unlink(missing_ok=True)
            except OSError:
                pass  # A cleanup error must not roll back an already running update.
        return 0
    except Exception as error:
        if stopped and target is not None:
            try:
                if backup is not None and backup.exists():
                    _replace(backup, target)
                elif installer_started and (not target.is_file() or file_digest(target) != value["original_sha256"]):
                    recovery = target.parent / (".clipboard-recovery-" + ticket.parent.name + ".exe")
                    if file_digest(ticket.parent / "runner.exe") != value["original_sha256"]:
                        raise UpdateError("recovery_failed")
                    shutil.copy2(ticket.parent / "runner.exe", recovery)
                    _replace(recovery, target)
                _shell_open(target, startup=True)
            except Exception:
                error = UpdateError("recovery_failed")
        try:
            _write_json(ticket.parent / "result.json", {"state": "failed",
                        "code": error.code if isinstance(error, UpdateError) else "install_failed",
                        "phase": phase, "error_type": type(error).__name__,
                        "winerror": getattr(error, "winerror", None) if isinstance(error, OSError) else None})
        except OSError:
            pass
        return 1
    finally:
        if parent_handle:
            _close_handle(parent_handle)
        if stage:
            try:
                stage.unlink(missing_ok=True)
            except OSError:
                pass


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != HELPER_FLAG:
        raise SystemExit(2)
    raise SystemExit(apply_ticket(sys.argv[2], Path(os.environ.get("LOCALAPPDATA", Path.home())) /
                                 "Clipboard Bridge" / "updates"))
