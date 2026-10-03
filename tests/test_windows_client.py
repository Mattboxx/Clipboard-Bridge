import base64
import importlib.util
import json
import os
import threading
import zipfile
import io
from types import SimpleNamespace
from pathlib import Path

import requests
import pytest


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

    assert client.APP_VERSION == "2.0.8"
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
        lambda item_id: (_ for _ in ()).throw(AssertionError("Use raw file downloads")),
    )
    monkeypatch.setattr(client.requests, "get", lambda *a, **kw: SimpleNamespace(
        content=b"%PDF-new", raise_for_status=lambda: None))
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
        "poll_latest",
        lambda known_id: {"id": "remote-text", "type": "text", "text": "From iPhone"},
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


def test_auto_sync_does_not_receive_or_upload_its_own_text_again(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    posts = []
    copied = []
    notifications = []

    class Response:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"id": "local-text"}

    class OneIteration:
        done = False

        def is_set(self):
            return self.done

        def wait(self, timeout):
            self.done = True

    def post(*args, **kwargs):
        posts.append((args, kwargs))
        return Response()

    client.config.update({
        "auto_sync": True,
        "auto_receive_files": False,
        "monitor_clipboard": False,
        "notifications_enabled": True,
        "notify_text": True,
    })
    monkeypatch.setattr(client.requests, "post", post)
    monkeypatch.setattr(client, "stop_event", OneIteration())
    monkeypatch.setattr(client, "check_connection", lambda: True)
    monkeypatch.setattr(client, "get_clipboard_files", lambda: [])
    monkeypatch.setattr(client, "get_clipboard_image", lambda: None)
    monkeypatch.setattr(client, "get_clipboard_text", lambda: "Sent from this PC")
    monkeypatch.setattr(
        client,
        "poll_latest",
        lambda known_id: {"id": "local-text", "type": "text", "text": "Sent from this PC"},
    )
    monkeypatch.setattr(client, "set_clipboard_text", lambda text: copied.append(text))
    monkeypatch.setattr(
        client,
        "notify",
        lambda message, action=None: notifications.append(message),
    )

    assert client.push_text("Sent from this PC") == "local-text"
    client.sync_loop()

    assert len(posts) == 1
    assert copied == []
    assert notifications == []


def test_last_handled_item_is_not_notified_again_after_restart(tmp_path, monkeypatch):
    first = load_client(tmp_path, monkeypatch)
    first.config.update({"server_ip": "10.0.0.10", "server_port": 5088})
    first._remember_item("already-seen")

    second = load_client(tmp_path, monkeypatch)
    copied = []
    notifications = []

    class OneIteration:
        done = False

        def is_set(self):
            return self.done

        def wait(self, timeout):
            self.done = True

    second.config.update({
        "server_ip": "10.0.0.10",
        "server_port": 5088,
        "auto_sync": True,
        "auto_receive_files": False,
        "monitor_clipboard": False,
    })
    monkeypatch.setattr(second, "stop_event", OneIteration())
    monkeypatch.setattr(second, "check_connection", lambda: True)
    monkeypatch.setattr(second, "get_clipboard_files", lambda: [])
    monkeypatch.setattr(second, "get_clipboard_image", lambda: None)
    monkeypatch.setattr(second, "get_clipboard_text", lambda: "")
    monkeypatch.setattr(
        second,
        "poll_latest",
        lambda known_id: {"id": "already-seen", "type": "text", "text": "Old text"},
    )
    monkeypatch.setattr(second, "set_clipboard_text", lambda text: copied.append(text))
    monkeypatch.setattr(
        second,
        "notify",
        lambda message, action=None: notifications.append(message),
    )

    second.sync_loop()

    assert copied == []
    assert notifications == []


def test_two_remote_file_items_leave_only_the_newest_on_clipboard(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    history = []
    clipboard_files = []
    notifications = []

    monkeypatch.setattr(client, "fetch_history", lambda limit=200: list(history))
    monkeypatch.setattr(
        client,
        "fetch_item",
        lambda item_id: (_ for _ in ()).throw(AssertionError("Use raw file downloads")),
    )
    monkeypatch.setattr(client.requests, "get", lambda url, **kw: SimpleNamespace(
        content=url.split("/")[-2].encode("ascii"), raise_for_status=lambda: None))
    monkeypatch.setattr(
        client,
        "set_clipboard_files",
        lambda paths: clipboard_files.append(list(paths)),
    )
    monkeypatch.setattr(
        client,
        "notify",
        lambda message, action=None: notifications.append(message),
    )

    assert client._auto_receive_remote_files() == []
    history.extend([
        {"id": "newest", "type": "file", "filename": "newest.pdf"},
        {"id": "older", "type": "file", "filename": "older.pdf"},
    ])

    received = client._auto_receive_remote_files()

    newest = str(Path(client.RECEIVED_DIR) / "newest.pdf")
    assert received == [newest]
    assert clipboard_files == [[newest]]
    assert (Path(client.RECEIVED_DIR) / "older.pdf").read_bytes() == b"older"
    assert (Path(client.RECEIVED_DIR) / "newest.pdf").read_bytes() == b"newest"
    assert len(notifications) == 2


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


def test_locally_uploaded_file_is_not_received_back_or_notified(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    notifications = []
    clipboard_files = []
    source = tmp_path / "local.pdf"
    source.write_bytes(b"local-file")
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
        assert client._auto_receive_remote_files() == []
        assert client.push_file(str(source))
        assert client._auto_receive_remote_files() == []
        assert notifications == []
        assert clipboard_files == []
        assert not Path(client.RECEIVED_DIR).exists()
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


def test_local_history_deduplicates_repeated_clipboard_items(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    client.record_local_file(str(first))
    client.record_local_file(str(first))
    client.record_local_files([str(first), str(second)])
    client.record_local_files([str(first), str(second)])
    image = client.Image.new("RGB", (8, 8), "red")
    client.record_local_image(image)
    client.record_local_image(image.copy())

    history = client._local_load()
    assert [item["type"] for item in history] == ["image", "bundle", "file"]
    assert len(list(Path(client.LOCAL_DIR).glob("*.png"))) == 1
    assert not Path(client.LOCAL_INDEX + ".tmp").exists()


def test_concurrent_local_history_updates_do_not_lose_entries(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    expected = {f"entry-{index}" for index in range(20)}
    threads = [
        threading.Thread(target=client.record_local_text, args=(text,))
        for text in expected
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    history = client._local_load()
    assert {item["text"] for item in history} == expected
    assert len(history) == len(expected)
    assert not Path(client.LOCAL_INDEX + ".tmp").exists()


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
    history.append({"id": "bundle-1", "type": "bundle", "file_count": 2,
                    "files": [{"index": 0, "filename": "one.txt"},
                              {"index": 1, "filename": "two.pdf"}]})
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


def test_windows_upload_preserves_unknown_extension_and_bytes(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    server = client.http.server.ThreadingHTTPServer(("127.0.0.1", 0), client._SrvHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    payload = b"AEA1\x00signed-shortcut-data"
    source = tmp_path / "Automation.shortcut"
    source.write_bytes(payload)
    client.config.update({
        "mode": "client",
        "server_ip": "127.0.0.1",
        "server_port": server.server_address[1],
        "token": "",
        "username": "",
        "password": "",
    })
    try:
        item_id = client.push_file(str(source))
        base = f"http://127.0.0.1:{server.server_address[1]}"
        history = requests.get(base + "/clipboard/history", timeout=5).json()["items"]
        assert history[0]["id"] == item_id
        assert history[0]["filename"] == "Automation.shortcut"
        assert history[0]["mime"] == "application/octet-stream"
        raw = requests.get(
            base + f"/clipboard/item/{item_id}/raw",
            timeout=5,
        )
        assert raw.content == payload
        assert raw.headers["X-Clipboard-Filename"] == "Automation.shortcut"
        assert raw.headers["Content-Disposition"].startswith("attachment;")

        iphone_payload = b"AEA1\x00iphone-shortcut"
        uploaded = requests.post(
            base + "/clipboard?filename=iPhone%20Automation.shortcut",
            data=iphone_payload,
            headers={"Content-Type": "application/octet-stream"},
            timeout=5,
        )
        uploaded.raise_for_status()
        latest = requests.get(base + "/clipboard/latest/raw", timeout=5)
        assert latest.content == iphone_payload
        assert latest.headers["X-Clipboard-Filename"] == "iPhone%20Automation.shortcut"
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


def test_unchanged_latest_poll_never_downloads_binary_content(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None,
                               json=lambda: {"id": "same", "type": "image", "size": 64000000})
    monkeypatch.setattr(client.requests, "get", get)
    for _ in range(5):
        assert "data" not in client.poll_latest("same")
    assert all(url.endswith("/clipboard/latest/meta") for url in calls)


def test_empty_file_download_is_valid_and_reused(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    item = {"id": "empty", "type": "file", "filename": "empty.shortcut", "data": ""}
    paths = client.save_remote_files(item)
    assert len(paths) == 1
    assert Path(paths[0]).read_bytes() == b""
    assert client.save_remote_files(item) == paths
    assert len(list(Path(client.RECEIVED_DIR).iterdir())) == 1


def test_old_file_download_does_not_replace_newer_text(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    history = []
    copied = []
    monkeypatch.setattr(client, "fetch_history", lambda limit: history)
    monkeypatch.setattr(client.requests, "get", lambda *a, **kw: SimpleNamespace(
        content=b"pdf", raise_for_status=lambda: None))
    monkeypatch.setattr(client, "set_clipboard_files", lambda paths: copied.append(paths))
    monkeypatch.setattr(client, "notify", lambda *a, **kw: None)
    client._auto_receive_remote_files()
    history.extend([{"id": "new-text", "type": "text"},
                    {"id": "old-file", "type": "file", "filename": "old.pdf"}])
    assert client._auto_receive_remote_files() == []
    assert copied == []
    assert client._last_remembered_item() is None
    assert (Path(client.RECEIVED_DIR) / "old.pdf").read_bytes() == b"pdf"


def test_busy_file_clipboard_retries_without_duplicate_download(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    history = []
    copies, downloads, notifications = [], [], []
    monkeypatch.setattr(client, "fetch_history", lambda limit: history)
    def get(*args, **kwargs):
        downloads.append(1)
        return SimpleNamespace(content=b"pdf", raise_for_status=lambda: None)
    def copy(paths):
        copies.append(paths)
        if len(copies) == 1:
            raise OSError("clipboard busy")
    monkeypatch.setattr(client.requests, "get", get)
    monkeypatch.setattr(client, "set_clipboard_files", copy)
    monkeypatch.setattr(client, "notify", lambda *a, **kw: notifications.append(1))
    client._auto_receive_remote_files()
    history.append({"id": "new", "type": "file", "filename": "new.pdf"})
    with pytest.raises(OSError):
        client._auto_receive_remote_files()
    assert client._last_remembered_item() is None
    assert client._auto_receive_remote_files() == copies[-1]
    assert len(downloads) == len(notifications) == 1
    assert client._last_remembered_item() == "new"


def test_interrupted_bundle_removes_partial_downloads(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    def member(item_id, index):
        if index == 1:
            raise requests.ConnectionError("interrupted")
        return "one.txt", b"one"
    monkeypatch.setattr(client, "fetch_bundle_member", member)
    bundle = {"id": "group", "type": "bundle", "files": [{"index": 0}, {"index": 1}]}
    with pytest.raises(requests.ConnectionError):
        client.save_remote_files(bundle)
    assert list(Path(client.RECEIVED_DIR).iterdir()) == []


def test_same_file_path_with_new_content_changes_clipboard_key(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    path = tmp_path / "notes.txt"
    path.write_bytes(b"old")
    before = client._file_clipboard_key([path])
    path.write_bytes(b"updated")
    assert client._file_clipboard_key([path]) != before


def test_manual_receive_does_not_reupload_and_failed_copy_is_not_remembered(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    item = {"id": "manual-text", "type": "text", "text": "received"}
    monkeypatch.setattr(client, "set_clipboard_text", lambda text: (_ for _ in ()).throw(OSError("busy")))
    with pytest.raises(OSError):
        client._copy_remote_item(item)
    assert client._last_remembered_item() is None
    monkeypatch.setattr(client, "set_clipboard_text", lambda text: None)
    assert client._copy_remote_item(item)
    assert client._take_local_upload_marker() == ("text", "received")


@pytest.mark.parametrize("operation", ["upload", "receive"])
def test_sync_retries_transient_clipboard_or_upload_failure(tmp_path, monkeypatch, operation):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(auto_sync=True, auto_receive_files=False, monitor_clipboard=False)
    class TwoIterations:
        count = 0
        def is_set(self): return self.count >= 2
        def wait(self, timeout): self.count += 1
    attempts, pulls = [], []
    def attempt(value):
        attempts.append(value)
        if len(attempts) == 1:
            raise OSError("temporarily unavailable")
        return "uploaded"
    monkeypatch.setattr(client, "stop_event", TwoIterations())
    monkeypatch.setattr(client, "check_connection", lambda: True)
    monkeypatch.setattr(client, "get_clipboard_files", lambda: None)
    monkeypatch.setattr(client, "get_clipboard_image", lambda: None)
    monkeypatch.setattr(client, "get_clipboard_text", lambda: "local" if operation == "upload" else "")
    monkeypatch.setattr(client, "push_text", attempt)
    monkeypatch.setattr(client, "set_clipboard_text", attempt)
    def poll(known_id):
        pulls.append(known_id)
        return {"id": "remote", "type": "text", "text": "remote"} if operation == "receive" else {"type": "empty"}
    monkeypatch.setattr(client, "poll_latest", poll)
    monkeypatch.setattr(client, "notify", lambda *a, **kw: None)
    client.sync_loop()
    assert len(attempts) == 2
    if operation == "upload":
        assert len(pulls) == 1  # failed local upload must not be overwritten remotely
    else:
        assert client._last_remembered_item() == "remote"


def test_unsupported_image_is_received_as_original_file(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    copied = []
    raw = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
    monkeypatch.setattr(client, "set_clipboard_files", lambda paths: copied.extend(paths))
    item = {"id": "svg", "type": "image", "filename": "drawing.svg",
            "data": base64.b64encode(raw).decode("ascii")}
    assert client._copy_remote_item(item) == "file"
    assert Path(copied[0]).read_bytes() == raw
    assert Path(copied[0]).suffix == ".svg"
    assert client._take_local_upload_marker()[0] == "files"


def test_long_unicode_filenames_are_safe_and_collisions_preserve_both_files(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    name = "\U0001f600" * 200 + ".shortcut"
    first = Path(client.save_received(name, b"first"))
    second = Path(client.save_received(name, b"second"))
    assert first != second
    assert first.suffix == second.suffix == ".shortcut"
    assert first.read_bytes() == b"first"
    assert second.read_bytes() == b"second"
    assert len(str(second).encode("utf-16-le")) // 2 < 260


def test_embedded_server_preserves_line_endings_utf32_and_literal_percent_names(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    text = "line1\r\nline2\rline3\n\u96ea"
    for encoding in ("utf-8", "utf-16", "utf-32"):
        assert client._host_decode_text(text.encode(encoding), "text/plain") == text
    saved = client._host_add("text", text)
    assert client._host_with_content(saved)["text"] == text
    assert (Path(client.HOST_ITEMS) / saved["file"]).read_bytes() == text.encode("utf-8")
    assert not Path(client.HOST_INDEX + ".tmp").exists()


def test_whitespace_text_can_be_sent_manually(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    sent = []
    monkeypatch.setattr(client, "get_clipboard_files", lambda: None)
    monkeypatch.setattr(client, "get_clipboard_image", lambda: None)
    monkeypatch.setattr(client, "get_clipboard_text", lambda: "\t \r\n ")
    monkeypatch.setattr(client, "push_text", lambda text: sent.append(text))
    monkeypatch.setattr(client, "notify", lambda *a, **kw: None)
    client.action_send_clipboard()
    assert sent == ["\t \r\n "]


def test_unchanged_clipboard_skips_repeated_bitmap_reads(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    reads = []
    client.config.update(auto_sync=False, auto_receive_files=False, monitor_clipboard=True)
    class TwoIterations:
        count = 0
        def is_set(self): return self.count >= 2
        def wait(self, timeout): self.count += 1
    monkeypatch.setattr(client, "stop_event", TwoIterations())
    monkeypatch.setattr(client, "check_connection", lambda: True)
    monkeypatch.setattr(client, "_clipboard_sequence", lambda: 123)
    monkeypatch.setattr(client, "get_clipboard_files", lambda: None)
    monkeypatch.setattr(client, "get_clipboard_image", lambda: reads.append(1))
    monkeypatch.setattr(client, "get_clipboard_text", lambda: "")
    client.sync_loop()
    assert reads == [1]


def test_unicode_token_uses_encoded_url_not_invalid_header(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    client.config["token"] = "\u96ea-\U0001f511"
    assert client.auth_headers() == {}
    assert client.auth_params()["token"] == client.config["token"]
