"""Verify native PyInstaller payloads and smoke-test a frozen Windows client."""

import argparse
import io
import json
import os
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader


MACHINES = {"x64": 0x8664, "arm64": 0xAA64}


def pe_machine(payload):
    with io.BytesIO(payload) as stream:
        assert stream.read(2) == b"MZ", "Not a Windows executable"
        stream.seek(0x3C)
        offset = struct.unpack("<I", stream.read(4))[0]
        stream.seek(offset)
        assert stream.read(4) == b"PE\0\0", "Missing PE header"
        return struct.unpack("<H", stream.read(2))[0]


def verify_payload(executable, architecture):
    machine = MACHINES[architecture]
    assert pe_machine(executable.read_bytes()) == machine, "Wrong executable architecture"
    archive = CArchiveReader(str(executable))
    libraries = [name for name in archive.toc if name.lower().endswith((".dll", ".pyd"))]
    assert libraries, "Missing bundled runtime"
    assert any(name.lower().endswith("pdfium.dll") for name in libraries), "Missing PDF renderer"
    assert any("licenses/" in name.replace("\\", "/").lower() for name in archive.toc), "Missing PDFium license notices"
    assert any("striprtf" in name.lower() and name.replace("\\", "/").lower().endswith("licenses/license")
               for name in archive.toc), "Missing RTF parser license"
    for name in libraries:
        assert pe_machine(archive.extract(name)) == machine, f"Wrong native architecture: {name}"
    print(f"Native {architecture} executable and {len(libraries)} bundled libraries: OK")


def smoke_test(executable):
    """Use a disposable profile; never read or modify the user's clipboard."""
    with tempfile.TemporaryDirectory(prefix="clipboard-build-check-") as folder:
        root = Path(folder)
        environment = os.environ.copy()
        for name in ("LOCALAPPDATA", "APPDATA", "USERPROFILE", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
            environment[name] = folder
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        data = root / "Clipboard Bridge"
        data.mkdir()
        (data / "config.json").write_text(json.dumps({
            "mode": "server", "host_port": port, "monitor_clipboard": False,
            "auto_sync": False, "auto_receive_files": False,
            "hotkeys_enabled": False, "notifications_enabled": False,
        }), encoding="utf-8")
        process = subprocess.Popen([str(executable)], cwd=root, env=environment)
        base = f"http://127.0.0.1:{port}"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            deadline = time.monotonic() + 60
            while True:
                try:
                    with opener.open(base + "/health", timeout=2) as response:
                        assert response.status == 200
                    break
                except (OSError, AssertionError):
                    if process.poll() is not None or time.monotonic() >= deadline:
                        log = data / "error.log"
                        raise AssertionError(log.read_text() if log.exists() else "Client did not start")
                    time.sleep(1)
            text = "Clipboard Bridge native test: caf\u00e9 \U0001f4cb"
            request = urllib.request.Request(base + "/clipboard", data=text.encode("utf-8"),
                                             headers={"Content-Type": "text/plain; charset=utf-8"})
            with opener.open(request, timeout=5) as response:
                assert response.status in (200, 201)
            with opener.open(base + "/clipboard/latest/raw", timeout=5) as response:
                assert response.read().decode("utf-8") == text
            request = urllib.request.Request(
                base + "/clipboard", data=rb"{\rtf1\ansi Caff\'e8 \u-10179?\u-8704?\par done}",
                headers={"Content-Type": "application/rtf"},
            )
            with opener.open(request, timeout=5) as response:
                assert json.load(response)["type"] == "text"
            with opener.open(base + "/clipboard/latest/raw", timeout=5) as response:
                assert response.read().decode("utf-8") == "Caff\u00e8 \U0001f600\ndone"
            with opener.open(base + "/clipboard/history", timeout=5) as response:
                assert response.read(), "Missing history"
            duplicate = subprocess.Popen([str(executable)], cwd=root, env=environment)
            try:
                assert duplicate.wait(timeout=30) == 0, "Duplicate instance failed"
                assert process.poll() is None, "Original instance unexpectedly stopped"
            finally:
                if duplicate.poll() is None:
                    subprocess.run(["taskkill", "/PID", str(duplicate.pid), "/T", "/F"], check=False)
            print("Frozen client startup, local server, Unicode/RTF, history and single instance: OK")
        finally:
            if process.poll() is None:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=True)
            process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--architecture", choices=MACHINES, required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    executable = args.executable.resolve(strict=True)
    verify_payload(executable, args.architecture)
    if args.smoke:
        smoke_test(executable)


if __name__ == "__main__":
    main()
