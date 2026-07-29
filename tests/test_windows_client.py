import base64
import importlib.util
import os
import threading
from pathlib import Path

import requests


def load_client(tmp_path, monkeypatch):
    local_app_data = tmp_path / "LocalAppData"
    user_profile = tmp_path / "User"
    (user_profile / "Downloads").mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setenv("USERPROFILE", str(user_profile))

    source = Path(__file__).parents[1] / "clipboard_bridge_windows.py"
    spec = importlib.util.spec_from_file_location("clipboard_bridge_windows_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_data_uses_user_writable_folders(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)

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

    # The first scan records existing history without downloading it.
    client._auto_receive_remote_files()
    assert not Path(client.RECEIVED_DIR).exists()

    history.insert(0, {"id": "new-file", "type": "file", "filename": "new-report.pdf"})
    client._auto_receive_remote_files()

    received = Path(client.RECEIVED_DIR) / "new-report.pdf"
    assert received.read_bytes() == b"%PDF-new"
    assert len(notifications) == 1
    assert callable(notifications[0][1])

    # A later scan must not save or notify the same server item again.
    client._auto_receive_remote_files()
    assert list(Path(client.RECEIVED_DIR).glob("new-report*")) == [received]
    assert len(notifications) == 1


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


def test_embedded_server_file_arrives_without_manual_receive(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    notifications = []
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

    try:
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
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
