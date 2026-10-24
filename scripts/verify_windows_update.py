"""Exercise the frozen updater only on a disposable CI Windows runner."""

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import clipboard_updates as updates


OLD_VERSION = "2.0.18"
OLD_HASHES = {
    "x64": "9350c62d325e3c8c9f709a7dd8b95cc50a87a316b6858529eb499427f1b4ab18",
    "arm64": "28bd03d34033496cddfe1a37495788641013f176519705dae83082faca65ae0d",
}


def wait_for_file(path, process, timeout=120):
    deadline = time.monotonic() + timeout
    while not path.exists():
        if process.poll() is not None or time.monotonic() >= deadline:
            result = path.parent / "result.json"
            detail = json.loads(result.read_text()) if result.exists() else {"exit_code": process.poll()}
            progress = path.parent / "progress.json"
            if progress.exists():
                detail["progress"] = json.loads(progress.read_text())
            raise AssertionError("Updater exited or timed out before writing " + path.name + ": " + json.dumps(detail))
        time.sleep(.2)
    return json.loads(path.read_text(encoding="utf-8"))


def exercise(old, executable, installer, architecture, root, kind):
    app = root / kind / "App folder & spaces"
    app.mkdir(parents=True)
    target = app / "Clipboard Bridge.exe"
    shutil.copy2(old, target)
    profile = root / kind / "profile"
    data = profile / "Clipboard Bridge"
    cache = data / "updates"
    folder = cache / uuid.uuid4().hex
    folder.mkdir(parents=True)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    config = data / "config.json"
    config.write_text(json.dumps({"mode": "server", "host_port": port, "lang": "en",
        "monitor_clipboard": False, "auto_sync": False, "auto_receive_files": False,
        "hotkeys_enabled": False, "notifications_enabled": False,
        "check_updates": False, "auto_install_updates": False}), encoding="utf-8")
    # Separate user-owned data must survive both updater paths.
    sample = data / "received_files" / "public-sample.bin"
    sample.parent.mkdir()
    sample.write_bytes(b"Public test data; preserve exactly.")
    before = {path: path.read_bytes() for path in (config, sample)}
    version = ".".join(map(str, updates.file_version(executable)))
    name = (f"Clipboard.Bridge.Portable.Windows.{architecture}.V{version}.exe" if kind == "portable"
            else f"Clipboard.Bridge_windows_client_and_server_setup_{architecture}_V{version}.exe")
    source = executable if kind == "portable" else installer
    payload = folder / name
    shutil.copy2(source, payload)
    candidate = updates.Update(version, architecture, kind, name,
        f"https://github.com/{updates.REPOSITORY}/releases/download/{version}/{name}",
        payload.stat().st_size, updates.file_digest(payload), updates.file_digest(executable))
    # Use the previous public helper too, matching the updater users already run.
    shutil.copy2(old, folder / "runner.exe")
    environment = os.environ.copy()
    for variable in ("LOCALAPPDATA", "APPDATA", "USERPROFILE", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        environment[variable] = str(profile)
    processes, restarted_pid = [], None
    try:
        parent = subprocess.Popen([str(target)], env=environment, cwd=app)
        processes.append(parent)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + 90
        while True:
            try:
                with opener.open(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                    assert response.status == 200
                break
            except OSError:
                assert parent.poll() is None and time.monotonic() < deadline, "Old frozen app did not start"
                time.sleep(.5)
        # PyInstaller's bootloader is the parent Popen PID. Its process image is
        # the same target and it exits only after its owned Python process exits.
        ticket = folder / "request.json"
        updates._write_json(ticket, {"schema": 1, "update": asdict(candidate), "target": str(target),
            "original_sha256": updates.file_digest(target), "parent_pid": parent.pid, "language": "en"})
        helper = subprocess.Popen([str(folder / "runner.exe"), updates.HELPER_FLAG, str(ticket)],
                                  env=environment, cwd=folder, creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(helper)
        assert wait_for_file(folder / "ready.json", helper)["state"] == "ready"
        assert updates.file_digest(target) == OLD_HASHES[architecture], "Replacement happened before parent exit"
        updates.commit_handoff(ticket)
        # Test harness only: terminate the exact disposable old process tree. The
        # production helper never kills applications and waits for graceful exit.
        subprocess.run(["taskkill", "/PID", str(parent.pid), "/T", "/F"], check=True, capture_output=True)
        parent.wait(timeout=15)
        result = wait_for_file(folder / "result.json", helper, timeout=180)
        restarted_pid = result.get("pid")
        assert result["state"] == "installed", result
        assert helper.wait(timeout=15) == 0
        updates.verify_executable(target, updates.file_digest(executable), version, architecture)
        assert all(path.read_bytes() == contents for path, contents in before.items()), "User data changed"
        with opener.open(f"http://127.0.0.1:{port}/health", timeout=10) as response:
            assert response.status == 200, "Updated client did not restart"
        print(f"Frozen {architecture} {kind}: {OLD_VERSION} -> {version}, restart and data preservation OK")
    finally:
        if restarted_pid:
            subprocess.run(["taskkill", "/PID", str(restarted_pid), "/T", "/F"], check=False, capture_output=True)
        for process in reversed(processes):
            if process.poll() is None:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False, capture_output=True)
            process.wait(timeout=15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("installer", type=Path)
    parser.add_argument("--architecture", choices=OLD_HASHES, required=True)
    args = parser.parse_args()
    if os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("This test installs only inside a disposable GitHub Actions Windows runner.")
    with tempfile.TemporaryDirectory(prefix="clipboard-update-check-", ignore_cleanup_errors=True) as temporary:
        root = Path(temporary)
        old = root / "previous.exe"
        url = (f"https://github.com/{updates.REPOSITORY}/releases/download/{OLD_VERSION}/"
               f"Clipboard.Bridge.Portable.Windows.{args.architecture}.V{OLD_VERSION}.exe")
        with updates._open(url) as response, old.open("xb") as output:
            shutil.copyfileobj(response, output)
        updates.verify_executable(old, OLD_HASHES[args.architecture], OLD_VERSION, args.architecture)
        for kind in ("portable", "installer"):
            exercise(old, args.executable.resolve(), args.installer.resolve(), args.architecture, root, kind)


if __name__ == "__main__":
    main()
