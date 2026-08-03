import base64
import importlib.util
import json
import os
import threading
import zipfile
import io
from pathlib import Path

import requests


def load_client(tmp_path, monkeypatch):
    local_app_data = tmp_path / "LocalAppData"
    user_profile = tmp_path / "User"
    (user_profile / "Downloads").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setenv("USERPROFILE", str(user_profile))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "Program Files"))
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "Program Files x86"))
    monkeypatch.setenv("ProgramW6432", str(tmp_path / "Program Files"))

    source = Path(__file__).parents[1] / "clipboard_bridge_windows.py"
    spec = importlib.util.spec_from_file_location("clipboard_bridge_windows_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_data_uses_user_writable_folders(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)

    assert client.APP_VERSION == "2.0.5"
    assert client.DATA_DIR == str(tmp_path / "LocalAppData" / "Clipboard Bridge")
    assert client.CONFIG_FILE.startswith(client.DATA_DIR)
    assert client.HOST_DIR.startswith(client.DATA_DIR)
    assert client.ERROR_LOG.startswith(client.DATA_DIR)
    assert client.RECEIVED_DIR == str(tmp_path / "User" / "Downloads" / "Clipboard Bridge")


def test_received_filename_cannot_escape_download_folder(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)

    saved = Path(client.save_received(r"..\..\report?.pdf", b"%PDF-test"))

    assert saved.parent == Path(client.RECEIVED_DIR)
    assert saved.name == "report_.pdf"
    assert saved.read_bytes() == b"%PDF-test"


def test_new_remote_pdf_is_downloaded_once(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    history = [
        {"id": "old-file", "type": "file", "filename": "old.pdf"},
    ]
    notifications = []
    clipboard_files = []

    monkeypatch.setattr(client, "fetch_history", lambda limit=200: list(history))
    monkeypatch.setattr(
        client,
        "fetch_item",
        lambda item_id: {
            "id": item_id,
            "type": "file",
            "filename": "new-report.pdf",
            "data": base64.b64encode(b"%PDF-new").decode("ascii"),
        },
    )
    monkeypatch.setattr(
        client,
        "notify",
        lambda message, action=None: notifications.append((message, action)),
    )
    monkeypatch.setattr(
        client,
        "set_clipboard_files",
        lambda paths: clipboard_files.append(list(paths)),
    )

    # The first scan records existing history without downloading it.
    assert client._auto_receive_remote_files() == []
    assert not Path(client.RECEIVED_DIR).exists()

    history.insert(0, {"id": "new-file", "type": "file", "filename": "new-report.pdf"})
    downloaded = client._auto_receive_remote_files()

    received = Path(client.RECEIVED_DIR) / "new-report.pdf"
    assert downloaded == [str(received)]
    assert received.read_bytes() == b"%PDF-new"
    assert len(notifications) == 1
    assert callable(notifications[0][1])
    assert clipboard_files == [[str(received)]]

    # A later scan must not save or notify the same server item again.
    assert client._auto_receive_remote_files() == []
    assert list(Path(client.RECEIVED_DIR).glob("new-report*")) == [received]
    assert len(notifications) == 1
    assert len(clipboard_files) == 1


def test_notification_click_runs_the_file_action(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    calls = []

    class FakeIcon:
        def __init__(self):
            self._message_handlers = {123: self._on_notify}

        @staticmethod
        def _on_notify(wparam, lparam):
            calls.append(("original", lparam))

    icon = FakeIcon()
    monkeypatch.setattr(client, "_run_bg", lambda action: action())
    client._install_notification_click_handler(icon)
    client.notify("file", action=lambda: calls.append(("file", None)))

    icon._message_handlers[123](0, 0x405)

    assert calls == [("file", None)]


def test_notification_master_switch_and_received_categories(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    original_notify = client.notify
    notifications = []
    monkeypatch.setattr(
        client,
        "notify",
        lambda message, action=None: notifications.append((message, action)),
    )

    client.config.update({
        "notifications_enabled": True,
        "notify_text": False,
        "notify_images": True,
        "notify_files": False,
    })
    client.notify_received("text", "text")
    client.notify_received("image", "image")
    client.notify_received("file", "file")

    assert notifications == [("image", None)]

    class FakeIcon:
        def __init__(self):
            self.messages = []

        def notify(self, message, title):
            self.messages.append((message, title))

    icon = FakeIcon()
    monkeypatch.setattr(client, "notify", original_notify)
    monkeypatch.setattr(client, "_icon", icon)
    client.config["notifications_enabled"] = False
    client.notify("hidden")
    assert icon.messages == []


def test_auto_sync_notifies_when_remote_text_is_copied(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    copied = []
    notifications = []

    class OneIteration:
        done = False

        def is_set(self):
            return self.done

        def wait(self, timeout):
            self.done = True

    client.config.update({
        "auto_sync": True,
        "auto_receive_files": False,
        "monitor_clipboard": False,
        "notifications_enabled": True,
        "notify_text": True,
    })
    monkeypatch.setattr(client, "stop_event", OneIteration())
    monkeypatch.setattr(client, "check_connection", lambda: True)
    monkeypatch.setattr(client, "get_clipboard_files", lambda: [])
    monkeypatch.setattr(client, "get_clipboard_image", lambda: None)
    monkeypatch.setattr(client, "get_clipboard_text", lambda: "")
    monkeypatch.setattr(
        client,
        "pull_latest",
        lambda: {"id": "remote-text", "type": "text", "text": "From iPhone"},
    )
    monkeypatch.setattr(client, "set_clipboard_text", lambda text: copied.append(text))
    monkeypatch.setattr(
        client,
        "notify",
        lambda message, action=None: notifications.append(message),
    )

    client.sync_loop()

    assert copied == ["From iPhone"]
    assert notifications == [client.t("text_arrived")]


def test_embedded_server_file_arrives_without_manual_receive(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    notifications = []
    clipboard_files = []
    server = client.http.server.ThreadingHTTPServer(("127.0.0.1", 0), client._SrvHandler)
    port = server.server_address[1]
    client.config.update({"mode": "server", "host_port": port})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        client,
        "notify",
        lambda message, action=None: notifications.append((message, action)),
    )
    monkeypatch.setattr(
        client,
        "set_clipboard_files",
        lambda paths: clipboard_files.append(list(paths)),
    )

    try:
        assert client.check_connection() is True
        assert client._connection_state == "connected"
        client._auto_receive_remote_files()  # empty baseline
        response = requests.post(
            f"http://127.0.0.1:{port}/clipboard/file",
            json={
                "filename": "iphone-document.pdf",
                "data": base64.b64encode(b"%PDF-from-iphone").decode("ascii"),
            },
            timeout=5,
        )
        response.raise_for_status()

        client._auto_receive_remote_files()

        received = Path(client.RECEIVED_DIR) / "iphone-document.pdf"
        assert received.read_bytes() == b"%PDF-from-iphone"
        assert len(notifications) == 1
        assert callable(notifications[0][1])
        assert clipboard_files == [[str(received)]]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_embedded_server_accepts_iphone_text_and_file_variants(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    server = client.http.server.ThreadingHTTPServer(("127.0.0.1", 0), client._SrvHandler)
    port = server.server_address[1]
    base = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        text = "Caffè ☕️\n中文 العربية\n👩‍💻"
        response = requests.post(
            base + "/clipboard",
            data=text.encode("utf-16"),
            headers={"Content-Type": "text/plain; charset=utf-16"},
            timeout=5,
        )
        response.raise_for_status()
        assert response.json()["type"] == "text"
        latest = requests.get(base + "/clipboard/latest/raw", timeout=5)
        assert latest.content == text.encode("utf-8")
        assert latest.headers["X-Clipboard-Type"] == "text"

        response = requests.post(base + "/clipboard", json=text, timeout=5)
        response.raise_for_status()
        assert requests.get(base + "/clipboard/latest/raw", timeout=5).text == text

        pdf = b"%PDF-1.7\n\x00binary\n%%EOF"
        response = requests.post(
            base + "/clipboard/file",
            data=pdf,
            headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": "attachment; filename*=UTF-8''scheda%20caff%C3%A8.pdf",
            },
            timeout=5,
        )
        response.raise_for_status()
        latest = requests.get(base + "/clipboard/latest/raw", timeout=5)
        assert latest.content == pdf
        assert latest.headers["X-Clipboard-Filename"] == "scheda%20caff%C3%A8.pdf"

        archive = b"PK\x03\x04\x00custom"
        response = requests.post(
            base + "/clipboard",
            files={"file": ("backup.unknown", archive, "application/x-custom")},
            timeout=5,
        )
        response.raise_for_status()
        assert response.json()["type"] == "file"
        latest = requests.get(base + "/clipboard/latest/raw", timeout=5)
        assert latest.content == archive
        assert latest.headers["Content-Type"] == "application/x-custom"

        image = b"\x89PNG\r\n\x1a\nimage"
        response = requests.post(
            base + "/clipboard",
            json={
                "filename": "photo.png",
                "data": "data:image/png;base64,"
                + base64.b64encode(image).decode("ascii"),
            },
            timeout=5,
        )
        response.raise_for_status()
        assert response.json()["type"] == "image"
        assert requests.get(base + "/clipboard/latest/raw", timeout=5).content == image

        response = requests.post(
            base + "/1",
            data="original shortcut",
            headers={"Content-Type": "text/plain; charset=utf-8"},
            timeout=5,
        )
        response.raise_for_status()
        assert requests.get(base + "/clipboard/raw", timeout=5).text == "original shortcut"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_file_clipboard_payload_uses_unicode_hdrop(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    first = tmp_path / "document one.pdf"
    second = tmp_path / "image.png"
    payload = client._build_hdrop([str(first), str(second)])
    header = client._DROPFILES.from_buffer_copy(payload)

    assert header.fWide
    assert header.pFiles == client.ctypes.sizeof(client._DROPFILES)
    names = payload[header.pFiles:].decode("utf-16-le").rstrip("\0").split("\0")
    assert names == [str(first.resolve()), str(second.resolve())]


def test_manual_receive_puts_file_on_clipboard(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    copied = []
    monkeypatch.setattr(
        client,
        "pull_latest",
        lambda: {
            "id": "manual-file",
            "type": "file",
            "filename": "manual.pdf",
            "data": base64.b64encode(b"%PDF-manual").decode("ascii"),
        },
    )
    monkeypatch.setattr(client, "set_clipboard_files", lambda paths: copied.append(list(paths)))
    monkeypatch.setattr(client, "notify", lambda *args, **kwargs: None)

    client.action_get_latest()

    received = Path(client.RECEIVED_DIR) / "manual.pdf"
    assert received.read_bytes() == b"%PDF-manual"
    assert copied == [[str(received)]]


def test_remote_file_bundle_is_restored_as_one_clipboard_group(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    history = []
    copied = []
    monkeypatch.setattr(client, "fetch_history", lambda limit=200: list(history))
    monkeypatch.setattr(
        client,
        "fetch_item",
        lambda item_id: {
            "id": item_id,
            "type": "bundle",
            "file_count": 2,
            "files": [
                {"index": 0, "filename": "one.txt"},
                {"index": 1, "filename": "two.pdf"},
            ],
        },
    )
    monkeypatch.setattr(
        client,
        "fetch_bundle_member",
        lambda item_id, index: (
            ("one.txt", b"one") if index == 0 else ("two.pdf", b"two")
        ),
    )
    monkeypatch.setattr(client, "set_clipboard_files", lambda paths: copied.append(list(paths)))
    monkeypatch.setattr(client, "notify", lambda *args, **kwargs: None)

    assert client._auto_receive_remote_files() == []
    history.append({"id": "bundle-1", "type": "bundle", "file_count": 2})
    downloaded = client._auto_receive_remote_files()

    assert [Path(path).name for path in downloaded] == ["one.txt", "two.pdf"]
    assert copied == [downloaded]
    local = client._local_load()
    assert len(local) == 1
    assert local[0]["type"] == "bundle"
    assert local[0]["file_count"] == 2


def test_windows_server_mode_keeps_multiple_files_in_one_item(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    server = client.http.server.ThreadingHTTPServer(("127.0.0.1", 0), client._SrvHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        response = requests.post(
            base + "/clipboard",
            files=[
                ("files", ("one.txt", b"one", "text/plain")),
                ("files", ("two.pdf", b"two", "application/pdf")),
            ],
            timeout=5,
        )
        response.raise_for_status()
        saved = response.json()
        assert saved["type"] == "bundle"
        assert saved["file_count"] == 2

        history = requests.get(base + "/clipboard/history", timeout=5).json()["items"]
        assert len(history) == 1
        assert history[0]["file_count"] == 2
        assert [item["filename"] for item in history[0]["files"]] == ["one.txt", "two.pdf"]

        first = requests.get(
            base + f"/clipboard/item/{saved['id']}/file/0/raw",
            timeout=5,
        )
        assert first.content == b"one"
        zipped = requests.get(base + "/clipboard/latest/raw", timeout=5)
        with zipfile.ZipFile(io.BytesIO(zipped.content)) as archive:
            assert archive.namelist() == ["one.txt", "two.pdf"]

        ios_archive = io.BytesIO()
        with zipfile.ZipFile(ios_archive, "w") as archive:
            archive.writestr("photo.jpg", b"photo")
            archive.writestr("documents/notes.txt", b"notes")
        ios_response = requests.post(
            base + "/clipboard/bundle",
            data=ios_archive.getvalue(),
            headers={"Content-Type": "application/zip"},
            timeout=5,
        )
        ios_response.raise_for_status()
        assert ios_response.json()["file_count"] == 2
        latest_meta = requests.get(base + "/clipboard/latest/meta", timeout=5).json()
        assert latest_meta["type"] == "bundle"
        assert [item["filename"] for item in latest_meta["files"]] == ["photo.jpg", "notes.txt"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_default_201_config_recovers_program_files_settings(tmp_path, monkeypatch):
    current_dir = tmp_path / "LocalAppData" / "Clipboard Bridge"
    current_dir.mkdir(parents=True)
    (current_dir / "config.json").write_text(
        json.dumps({
            "mode": "client",
            "server_ip": "127.0.0.1",
            "server_port": 5088,
            "host_port": 5088,
            "token": "",
            "username": "",
            "password": "",
            "lang": "en",
        }),
        encoding="utf-8",
    )
    legacy_dir = tmp_path / "Program Files" / "Clipboard Bridge"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "config.json").write_text(
        json.dumps({
            "server_ip": "192.168.1.40",
            "server_port": 5088,
            "token": "legacy-token",
            "username": "alice",
            "password": "legacy-password",
            "auto_sync": True,
            "lang": "it",
        }),
        encoding="utf-8",
    )

    client = load_client(tmp_path, monkeypatch)

    assert client.config["server_ip"] == "192.168.1.40"
    assert client.config["token"] == "legacy-token"
    assert client.config["username"] == "alice"
    assert client.config["password"] == "legacy-password"
    assert client.config["auto_sync"] is True
    assert client.config["lang"] == "it"
    assert client.config["_legacy_migration_version"] == 2


def test_connection_check_distinguishes_connected_and_rejected(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)

    class Response:
        def __init__(self, status):
            self.status_code = status

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(str(self.status_code))

        @staticmethod
        def json():
            return {"items": [], "count": 0}

    monkeypatch.setattr(client.requests, "get", lambda *args, **kwargs: Response(200))
    assert client.check_connection() is True
    assert client._connection_state == "connected"
    assert "CONNECTED" in client.connection_status_text()

    monkeypatch.setattr(client.requests, "get", lambda *args, **kwargs: Response(401))
    assert client.check_connection() is False
    assert client._connection_state == "auth"
    assert "LOGIN REJECTED" in client.connection_status_text()


def test_tray_connection_text_is_compact_and_colored(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)

    client._set_connection_state("connected")
    assert client.tray_connection_text() == "\U0001f7e2 Connected"

    client._set_connection_state("offline")
    assert client.tray_connection_text() == "\U0001f534 Disconnected"


def test_connection_check_uses_pending_settings(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    request_data = {}

    class Response:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"items": [], "count": 0}

    def fake_get(url, **kwargs):
        request_data["url"] = url
        request_data.update(kwargs)
        return Response()

    monkeypatch.setattr(client.requests, "get", fake_get)
    settings = dict(client.config)
    settings.update({
        "mode": "client",
        "server_ip": "10.0.0.25",
        "server_port": 5099,
        "username": "alice",
        "password": "secret",
        "token": "api-token",
    })

    assert client.check_connection(settings) is True
    assert request_data["url"] == "http://10.0.0.25:5099/clipboard/history"
    assert request_data["params"] == {
        "limit": 1,
        "user": "alice",
        "password": "secret",
    }
    assert request_data["headers"] == {"X-Auth-Token": "api-token"}


def test_windows_single_instance_mutex_blocks_duplicate(tmp_path, monkeypatch):
    if os.name != "nt":
        return

    first = load_client(tmp_path, monkeypatch)
    second = load_client(tmp_path, monkeypatch)
    mutex_name = f"Local\\ClipboardBridge.Test.{os.getpid()}.{id(first)}"

    assert first._acquire_single_instance(mutex_name) is True
    try:
        assert second._acquire_single_instance(mutex_name) is False
    finally:
        first._release_single_instance()
        second._release_single_instance()

    assert second._acquire_single_instance(mutex_name) is True
    second._release_single_instance()
