import base64
import importlib.util
import io
import sys
import uuid
from pathlib import Path

import pytest


SERVER_FILE = Path(__file__).resolve().parents[1] / "clipboard_bridge-Server.py"


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIPBOARD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CLIPBOARD_TOKEN", "shared-token")
    monkeypatch.setenv("CLIPBOARD_PASSWORD", "shared-web-password")
    monkeypatch.setenv("CLIPBOARD_ACCOUNTS", "alice:p&ss?word,bob:second")
    monkeypatch.setenv("CLIPBOARD_MAX_HISTORY", "3")
    monkeypatch.setenv("CLIPBOARD_MAX_UPLOAD_MB", "1")

    module_name = "clipboard_bridge_server_test_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(module_name, SERVER_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    module.app.config.update(TESTING=True)
    yield module
    sys.modules.pop(module_name, None)


def test_shared_clipboard_and_security_headers(server):
    client = server.app.test_client()
    auth = {"X-Auth-Token": "shared-token", "Content-Type": "text/plain"}

    response = client.post("/clipboard", data="hello", headers=auth)
    assert response.status_code == 200
    assert response.get_json()["type"] == "text"

    response = client.get("/clipboard/latest/raw?token=shared-token")
    assert response.data == b"hello"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_accounts_are_isolated_and_support_url_or_headers(server):
    client = server.app.test_client()

    response = client.post(
        "/clipboard?user=alice&password=p%26ss%3Fword",
        data="alice item",
        content_type="text/plain",
    )
    assert response.status_code == 200

    response = client.post(
        "/clipboard",
        data="bob item",
        content_type="text/plain",
        headers={
            "X-Clipboard-User": "bob",
            "X-Clipboard-Password": "second",
        },
    )
    assert response.status_code == 200

    alice = client.get("/clipboard/latest/raw?user=alice&password=p%26ss%3Fword")
    bob = client.get(
        "/clipboard/latest/raw",
        headers={
            "X-Clipboard-User": "bob",
            "X-Clipboard-Password": "second",
        },
    )
    shared = client.get("/clipboard/latest/raw?token=shared-token")
    assert alice.data == b"alice item"
    assert bob.data == b"bob item"
    assert shared.data == b""


def test_iphone_style_binary_round_trip(server):
    client = server.app.test_client()
    payload = b"%PDF-1.4\nclipboard bridge test\n%%EOF"
    account_url = "?user=alice&password=p%26ss%3Fword"

    response = client.post(
        "/clipboard" + account_url,
        data=payload,
        content_type="application/pdf",
        headers={"X-Filename": "document.pdf"},
    )
    assert response.status_code == 200
    assert response.get_json()["type"] == "file"

    response = client.get("/clipboard/latest/raw" + account_url)
    assert response.status_code == 200
    assert response.data == payload
    assert response.mimetype == "application/pdf"
    assert "document.pdf" in response.headers["Content-Disposition"]


def test_original_published_shortcut_routes_remain_compatible(server):
    client = server.app.test_client()

    response = client.post(
        "/1?token=shared-token",
        data="original shortcut",
        content_type="text/plain; charset=utf-8",
    )
    assert response.status_code == 200
    assert response.get_json()["type"] == "text"

    latest = client.get("/clipboard/raw?token=shared-token")
    assert latest.status_code == 200
    assert latest.data == b"original shortcut"
    assert latest.headers["X-Clipboard-Type"] == "text"


def test_iphone_text_variants_preserve_every_character(server):
    client = server.app.test_client()
    url = "/clipboard?token=shared-token"
    text = "Caffè ☕️\n中文 العربية\nemoji: 👩‍💻\tend\x00"
    cases = (
        {"data": text.encode("utf-8"), "content_type": "text/plain; charset=utf-8"},
        {"data": text.encode("utf-16"), "content_type": "text/plain; charset=utf-16"},
        {"json": text},
        {"json": {"value": text}},
        {"data": {"clipboard": text}},
    )

    for posted in cases:
        response = client.post(url, **posted)
        assert response.status_code == 200
        assert response.get_json()["type"] == "text"

        latest = client.get("/clipboard/latest/raw?token=shared-token")
        assert latest.data == text.encode("utf-8")
        assert latest.headers["X-Clipboard-Type"] == "text"
        assert latest.headers["X-Clipboard-Id"] == response.get_json()["id"]
        assert latest.content_type == "text/plain; charset=utf-8"

    empty = client.post(url, data=b"", content_type="text/plain")
    assert empty.status_code == 200
    assert client.get("/clipboard/latest/raw?token=shared-token").data == b""


def test_file_endpoint_accepts_raw_multipart_json_and_empty_files(server):
    client = server.app.test_client()
    token = "?token=shared-token"

    pdf = b"%PDF-1.7\nbinary\x00content\n%%EOF"
    response = client.post(
        "/clipboard/file" + token,
        data=pdf,
        content_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename*=UTF-8''scheda%20caff%C3%A8.pdf"},
    )
    assert response.status_code == 200
    latest = client.get("/clipboard/latest/raw" + token)
    assert latest.data == pdf
    assert latest.mimetype == "application/pdf"
    assert latest.headers["X-Clipboard-Filename"] == "scheda%20caff%C3%A8.pdf"
    assert "filename*=UTF-8''scheda%20caff%C3%A8.pdf" in latest.headers["Content-Disposition"]

    archive = b"PK\x03\x04\x00\xff\x10zip"
    response = client.post(
        "/clipboard/file" + token,
        data={"anything": (io.BytesIO(archive), "backup.custom-archive", "application/x-custom")},
    )
    assert response.status_code == 200
    latest = client.get("/clipboard/latest/raw" + token)
    assert latest.data == archive
    assert latest.mimetype == "application/x-custom"

    pages = b"IWA\x00Apple Pages test"
    encoded = base64.urlsafe_b64encode(pages).decode("ascii").rstrip("=")
    response = client.post(
        "/clipboard/file" + token,
        json={
            "filename": "document.pages",
            "mime": "application/vnd.apple.pages",
            "data": encoded,
        },
    )
    assert response.status_code == 200
    latest = client.get("/clipboard/latest/raw" + token)
    assert latest.data == pages
    assert latest.mimetype == "application/vnd.apple.pages"

    response = client.post(
        "/clipboard/file" + token,
        data=b"",
        content_type="application/octet-stream",
        headers={"X-Filename": "empty.unknown"},
    )
    assert response.status_code == 200
    latest = client.get("/clipboard/latest/raw" + token)
    assert latest.data == b""
    assert latest.headers["X-Clipboard-Filename"] == "empty.unknown"


def test_universal_endpoint_accepts_data_urls_and_sanitizes_names(server):
    client = server.app.test_client()
    raw = b"\x89PNG\r\n\x1a\nclipboard"
    data_url = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")

    response = client.post(
        "/clipboard?token=shared-token",
        json={"filename": r"..\..\foto vacanza.png", "data": data_url},
    )
    assert response.status_code == 200
    assert response.get_json()["type"] == "image"

    latest = client.get("/clipboard/latest?token=shared-token").get_json()
    assert latest["filename"] == "foto vacanza.png"
    assert latest["mime"] == "image/png"
    assert base64.b64decode(latest["data"]) == raw


def test_octet_stream_with_filename_is_never_changed_into_text(server):
    client = server.app.test_client()
    payload = b"this file happens to contain only printable ASCII"

    response = client.post(
        "/clipboard?token=shared-token",
        data=payload,
        content_type="application/octet-stream",
        headers={"X-File-Name": "important.dat"},
    )

    assert response.status_code == 200
    assert response.get_json()["type"] == "file"
    assert client.get("/clipboard/latest/raw?token=shared-token").data == payload

    response = client.post(
        "/clipboard?token=shared-token",
        data=payload,
        content_type="application/octet-stream",
    )
    assert response.status_code == 200
    assert response.get_json()["type"] == "file"
    assert client.get("/clipboard/latest/raw?token=shared-token").data == payload


def test_readable_files_keep_their_file_type(server):
    client = server.app.test_client()
    token = "?token=shared-token"
    cases = (
        ("settings.json", "application/json", b'{"data":"this is a real JSON file"}'),
        ("drawing.svg", "image/svg+xml", b"<svg><rect width='10' height='10'/></svg>"),
        ("notes.txt", "text/plain", b"this is a text file, not clipboard text"),
    )

    for filename, mime, payload in cases:
        response = client.post(
            "/clipboard" + token,
            data=payload,
            content_type=mime,
            headers={"X-Filename": filename},
        )
        assert response.status_code == 200
        expected_type = "image" if mime.startswith("image/") else "file"
        assert response.get_json()["type"] == expected_type

        latest = client.get("/clipboard/latest/raw" + token)
        assert latest.data == payload
        assert latest.headers["X-Clipboard-Filename"] == filename


def test_web_login_builds_encoded_shortcut_urls(server):
    client = server.app.test_client()
    response = client.post(
        "/login",
        data={"username": "alice", "password": "p&ss?word"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "?user=alice&amp;password=p%26ss%3Fword" in html
    assert "p&ss?word" not in html


def test_history_limit_and_upload_limit(server):
    client = server.app.test_client()
    headers = {"X-Auth-Token": "shared-token", "Content-Type": "text/plain"}
    for value in ("one", "two", "three", "four"):
        assert client.post("/clipboard", data=value, headers=headers).status_code == 200

    history = client.get("/clipboard/history?token=shared-token").get_json()
    assert history["count"] == 3

    response = client.post(
        "/clipboard?token=shared-token",
        data=b"x" * (1024 * 1024 + 1),
        content_type="application/octet-stream",
    )
    assert response.status_code == 413
    assert response.get_json()["max_upload_mb"] == 1


def test_health_reports_server_version(server):
    response = server.app.test_client().get("/health")
    assert response.status_code == 200
    assert response.get_json()["version"] == "1.0.2"
