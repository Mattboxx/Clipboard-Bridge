"""Run native clipboard checks in a new process with a private window station.

Never use a separate desktop alone: desktops in one station share its clipboard.
This worker never switches back to the interactive station. Process exit releases
the private station/desktop handles, including on failure.
"""

import argparse
import ctypes
from ctypes import wintypes
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import uuid


def bind(library, name, arguments, result):
    function = getattr(library, name)
    function.argtypes = arguments
    function.restype = result
    return function


def isolate_clipboard():
    user = ctypes.WinDLL("user32", use_last_error=True)
    create_station = bind(user, "CreateWindowStationW",
                          [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p], wintypes.HANDLE)
    set_station = bind(user, "SetProcessWindowStation", [wintypes.HANDLE], wintypes.BOOL)
    get_station = bind(user, "GetProcessWindowStation", [], wintypes.HANDLE)
    information = bind(user, "GetUserObjectInformationW",
                       [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                        ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL)
    name = "ClipboardBridgeTest_" + uuid.uuid4().hex
    station = create_station(name, 1, 0x10000000, None)  # CREATE_ONLY, GENERIC_ALL
    if not station and ctypes.get_last_error() == 5:
        # Non-admin users may create only a system-named station. CREATE_ONLY
        # still refuses an existing station; never attach to a shared fallback.
        name = None
        station = create_station(None, 1, 0x10000000, None)
    if not station:
        raise OSError(ctypes.get_last_error(), "private window station unavailable")
    if not set_station(station):
        raise OSError(ctypes.get_last_error(), "cannot select private window station")
    actual = ctypes.create_unicode_buffer(256)
    needed = wintypes.DWORD()
    if not information(get_station(), 2, actual, ctypes.sizeof(actual), ctypes.byref(needed)):
        raise OSError(ctypes.get_last_error(), "cannot verify private window station")
    if not actual.value or (name is not None and actual.value != name) or actual.value.lower() == "winsta0":
        raise RuntimeError("clipboard isolation was not established")
    create_desktop = bind(user, "CreateDesktopW",
                          [wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                           wintypes.DWORD, ctypes.c_void_p], wintypes.HANDLE)
    set_desktop = bind(user, "SetThreadDesktop", [wintypes.HANDLE], wintypes.BOOL)
    desktop = create_desktop("Default", None, None, 0, 0x10000000, None)
    if not desktop or not set_desktop(desktop):
        raise OSError(ctypes.get_last_error(), "cannot select private desktop")
    return user


def read_payload(user, format_id, length):
    open_clipboard = bind(user, "OpenClipboard", [wintypes.HWND], wintypes.BOOL)
    close_clipboard = bind(user, "CloseClipboard", [], wintypes.BOOL)
    get_data = bind(user, "GetClipboardData", [wintypes.UINT], wintypes.HANDLE)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    lock = bind(kernel, "GlobalLock", [wintypes.HANDLE], ctypes.c_void_p)
    unlock = bind(kernel, "GlobalUnlock", [wintypes.HANDLE], wintypes.BOOL)
    size = bind(kernel, "GlobalSize", [wintypes.HANDLE], ctypes.c_size_t)
    if not open_clipboard(None):
        raise OSError("cannot read private clipboard")
    try:
        handle = get_data(format_id)
        if not handle or size(handle) < length:
            raise AssertionError("private clipboard has no complete payload")
        pointer = lock(handle)
        if not pointer:
            raise OSError("cannot lock private clipboard payload")
        try:
            return ctypes.string_at(pointer, length)
        finally:
            unlock(handle)
    finally:
        close_clipboard()


def in_worker_thread(operation):
    errors = []

    def run():
        try:
            operation()
        except BaseException as error:
            errors.append(error)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout=10)
    if worker.is_alive():
        raise AssertionError("clipboard worker did not finish")
    if errors:
        raise errors[0]


def run_checks(source_root, user):
    with tempfile.TemporaryDirectory(prefix="clipboard-native-profile-") as folder:
        root = Path(folder)
        for name in ("LOCALAPPDATA", "APPDATA", "USERPROFILE", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
            os.environ[name] = folder
        app = root / "app"
        app.mkdir()
        for name in ("clipboard_bridge_windows.py", "clipboard_text.py", "clipboard_storage.py", "clipboard_updates.py", "clipboard_design.py", "VERSION"):
            shutil.copy2(source_root / name, app / name)
        sys.path.insert(0, str(app))
        spec = importlib.util.spec_from_file_location("clipboard_native_test", app / "clipboard_bridge_windows.py")
        client = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(client)
        image = client.Image.new("RGB", (3, 2))
        image.putdata([(200, 40, 120), (0, 255, 0), (0, 0, 255),
                       (40, 20, 10), (240, 210, 100), (255, 255, 255)])
        encoded = io.BytesIO()
        image.save(encoded, "BMP")
        dib = encoded.getvalue()[14:]
        in_worker_thread(lambda: client.set_clipboard_image(image))
        actual = read_payload(user, 8, len(dib))
        assert actual == dib, "DIB bytes changed"
        with client.Image.open(io.BytesIO(actual)) as restored:
            assert restored.convert("RGB").tobytes() == image.tobytes(), "Image pixels changed"
        paths = [root / "public-one.pdf", root / "caf\u00e9-\U0001f600.txt"]
        for path in paths:
            path.write_bytes(b"Public synthetic test file")
        filenames = list(map(str, paths))
        expected = client._build_hdrop(filenames)
        in_worker_thread(lambda: client.set_clipboard_files(filenames))
        assert read_payload(user, 15, len(expected)) == expected, "HDROP paths changed"
        print(json.dumps({"status": "passed", "private_station": True,
                          "image_pixels": True, "unicode_file_group": True,
                          "background_threads": True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    if sys.platform != "win32":
        return 77
    try:
        user = isolate_clipboard()
    except OSError as error:
        print(json.dumps({"status": "unavailable", "reason": "private_clipboard_unavailable",
                          "error_code": error.errno}))
        return 77
    run_checks(args.source_root.resolve(), user)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
