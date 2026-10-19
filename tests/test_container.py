"""Opt-in tests of a disposable Docker host; never use a user's existing data.

Build an image, then set CLIPBOARD_TEST_IMAGE to its local tag. Each test module
owns a unique container and volume and removes only those named resources.
"""

import io
import http.cookiejar
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

import pytest


IMAGE = os.environ.get("CLIPBOARD_TEST_IMAGE")
pytestmark = pytest.mark.skipif(not IMAGE, reason="No disposable container image configured")


def docker(*arguments, check=True):
    result = subprocess.run(["docker", *arguments], text=True, capture_output=True,
                            timeout=90, check=check)
    return result.stdout.strip()


class ContainerHost:
    def __init__(self, name, volume):
        self.name, self.volume = name, volume
        self.base = ""

    def start(self):
        docker("run", "--detach", "--name", self.name,
               "--label", "io.clipboard-bridge.test=storage",
               "--publish", "127.0.0.1::5088",
               "--mount", f"type=volume,source={self.volume},target=/data",
               "--env", "CLIPBOARD_MAX_UPLOAD_MB=4",
               "--env", "CLIPBOARD_ACCOUNTS=alice:test-password,bob:other-password",
               IMAGE)
        self.wait_ready()

    def wait_ready(self):
        # Docker can assign a different dynamic host port after restart/recreation.
        self.base = "http://" + docker("port", self.name, "5088/tcp").splitlines()[0]
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            try:
                status, _, body = self.request("GET", "/health")
                if status == 200 and json.loads(body)["status"] == "ok":
                    return
            except (OSError, ValueError):
                pass
            time.sleep(0.2)
        raise AssertionError("Disposable container did not become ready")

    def restart(self):
        docker("restart", self.name)
        self.wait_ready()

    def recreate(self):
        docker("rm", "--force", self.name)
        self.start()

    def request(self, method, route, data=None, content_type="text/plain; charset=utf-8",
                account=None, headers=None, **query):
        if account:
            query.update(user=account, password="test-password" if account == "alice" else "other-password")
        url = self.base + route + ("?" + urllib.parse.urlencode(query) if query else "")
        request = urllib.request.Request(url, data=data, method=method,
                                         headers={"Content-Type": content_type, **(headers or {})})
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read()


@pytest.fixture(scope="module")
def container_host():
    name = "clipboard-test-" + uuid.uuid4().hex
    volume = name + "-data"
    docker("volume", "create", "--label", "io.clipboard-bridge.test=storage", volume)
    host = ContainerHost(name, volume)
    try:
        host.start()
        yield host
    finally:
        # No prune, production container names, host directories or user volumes.
        try:
            docker("rm", "--force", name, check=False)
        finally:
            docker("volume", "rm", volume, check=False)


def test_container_transfers_latest_groups_and_account_isolation(container_host):
    host = container_host
    text = "Clipboard sample \U0001f680\nCaff\u00e8\r\n\t"
    assert host.request("POST", "/clipboard", text.encode())[0] == 200
    assert host.request("GET", "/clipboard/latest/raw")[2] == text.encode()
    raw = b"AEA1\x00\xff\x00original-file"
    status, _, response = host.request("POST", "/clipboard", raw, "application/octet-stream",
                                       account="alice", filename="workflow.shortcut")
    assert status == 200
    item_id = json.loads(response)["id"]
    assert host.request("GET", "/clipboard/latest/raw", account="alice")[2] == raw
    assert host.request("GET", f"/clipboard/item/{item_id}/raw", account="bob")[0] == 404
    assert host.request("GET", "/clipboard/latest/raw")[2] == text.encode()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as files:
        files.writestr("photo.png", b"test-image-bytes")
        files.writestr("notes.txt", text.encode())
    status, _, response = host.request("POST", "/clipboard/bundle", archive.getvalue(),
                                       "application/zip", account="alice")
    assert status == 200 and json.loads(response)["file_count"] == 2
    group_id = json.loads(response)["id"]
    history = json.loads(host.request("GET", "/clipboard/history", account="alice")[2])
    assert history["items"][0]["id"] == group_id
    assert history["items"][0]["type"] == "bundle"
    with zipfile.ZipFile(io.BytesIO(host.request("GET", "/clipboard/latest/raw", account="alice")[2])) as files:
        assert files.read("notes.txt") == text.encode()
        assert files.read("photo.png") == b"test-image-bytes"
    host.request("POST", "/clipboard", b"newest text", account="alice")
    assert host.request("GET", "/clipboard/latest/raw", account="alice")[2] == b"newest text"
    assert host.request("POST", "/clipboard", b"x" * (4 * 1024 * 1024 + 1))[0] == 413


def test_container_restart_and_recreation_preserve_files_and_web_session(container_host):
    host = container_host
    payload = b"persistent file sample"
    assert host.request("POST", "/clipboard", payload, "application/octet-stream",
                        filename="sample.pdf", account="alice")[0] == 200
    login = urllib.parse.urlencode({"username": "alice", "password": "test-password"}).encode()
    # urllib follows the login redirect; keep its session cookie across restarts.
    cookies = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    with opener.open(host.base + "/login", data=login, timeout=5) as response:
        assert response.status == 200
    cookie = "; ".join(f"{item.name}={item.value}" for item in cookies)
    assert cookie
    for action in (host.restart, host.recreate):
        action()
        assert host.request("GET", "/clipboard/latest/raw", account="alice")[2] == payload
        assert host.request("GET", "/clipboard/latest/raw", headers={"Cookie": cookie})[2] == payload


def test_container_refuses_damaged_history_without_erasing_data(container_host):
    host = container_host
    assert host.request("POST", "/clipboard", b"before corruption")[0] == 200
    docker("exec", host.name, "python", "-c",
           "from pathlib import Path; p=Path('/data/index.json'); "
           "Path('/data/index.test-backup').write_bytes(p.read_bytes()); p.write_bytes(b'{damaged')")
    try:
        for method, route in (("GET", "/health"), ("GET", "/clipboard/history"),
                              ("POST", "/clipboard"), ("DELETE", "/clipboard/history")):
            status, _, body = host.request(method, route, b"new item" if method == "POST" else None)
            assert status == 503 and json.loads(body)["code"] == "history_unavailable"
        assert docker("exec", host.name, "python", "-c",
                      "from pathlib import Path; print(Path('/data/index.json').read_text())") == "{damaged"
        assert host.request("GET", "/clipboard/latest/raw", account="alice")[0] == 200
    finally:
        docker("exec", host.name, "python", "-c",
               "from pathlib import Path; p=Path('/data/index.test-backup'); "
               "Path('/data/index.json').write_bytes(p.read_bytes()); p.unlink()")
    assert host.request("GET", "/clipboard/latest/raw")[2] == b"before corruption"


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows client integration")
def test_windows_client_uses_disposable_container(container_host, tmp_path, monkeypatch):
    from test_live_server import assert_windows_round_trips
    assert_windows_round_trips(container_host.base, tmp_path, monkeypatch)
