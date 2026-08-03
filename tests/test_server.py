import base64
import importlib.util
import io
import sys
import uuid
import zipfile
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


def test_latest_item_follows_arrival_order_regardless_of_type(server):
    client = server.app.test_client()
    token = "?token=shared-token"

    first_file = client.post(
        "/clipboard" + token,
        data=b"\x01\x02\x03",
        content_type="application/octet-stream",
        headers={"X-Clipboard-Filename": "first.bin"},
    ).get_json()
    newest_text = client.post(
        "/clipboard" + token,
        data="newest text",
        content_type="text/plain; charset=utf-8",
    ).get_json()

    history = client.get("/clipboard/history" + token).get_json()["items"]
    assert [item["id"] for item in history[:2]] == [newest_text["id"], first_file["id"]]
    assert client.get("/clipboard/latest/raw" + token).data == b"newest text"

    newest_file = client.post(
        "/clipboard" + token,
        data=b"\x10\x20\x30",
        content_type="application/octet-stream",
        headers={"X-Clipboard-Filename": "newest.bin"},
    ).get_json()

    latest = client.get("/clipboard/latest" + token).get_json()
    assert latest["id"] == newest_file["id"]
    assert latest["type"] == "file"
    assert client.get("/clipboard/latest/raw" + token).data == b"\x10\x20\x30"


def test_multiple_files_are_one_history_bundle(server):
    client = server.app.test_client()
    token = "?token=shared-token"
    response = client.post(
        "/clipboard" + token,
        data={
            "files": [
                (io.BytesIO(b"first document"), "notes.txt"),
                (io.BytesIO(b"%PDF-second"), "report.pdf"),
            ],
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    saved = response.get_json()
    assert saved["type"] == "bundle"
    assert saved["file_count"] == 2

    history = client.get("/clipboard/history" + token).get_json()["items"]
    assert len(history) == 1
    assert history[0]["id"] == saved["id"]
    assert history[0]["file_count"] == 2
    assert [item["filename"] for item in history[0]["files"]] == ["notes.txt", "report.pdf"]

    first = client.get(f"/clipboard/item/{saved['id']}/file/0/raw{token}")
    second = client.get(f"/clipboard/item/{saved['id']}/file/1/raw{token}")
    assert first.data == b"first document"
    assert second.data == b"%PDF-second"

    zipped = client.get("/clipboard/latest/raw" + token)
    assert zipped.headers["X-Clipboard-Type"] == "bundle"
    with zipfile.ZipFile(io.BytesIO(zipped.data)) as archive:
        assert archive.namelist() == ["notes.txt", "report.pdf"]
        assert archive.read("notes.txt") == b"first document"
    first.close()
    second.close()
    zipped.close()

    assert client.delete(f"/clipboard/item/{saved['id']}{token}").status_code == 200
    assert list((Path(server.DATA_DIR) / "items").glob(f"{saved['id']}_*")) == []


def test_ios_zip_transport_becomes_a_real_file_group(server):
    client = server.app.test_client()
    archive_data = io.BytesIO()
    with zipfile.ZipFile(archive_data, "w") as archive:
        archive.writestr("Photos/holiday.jpg", b"jpeg-data")
        archive.writestr("../unsafe/report.pdf", b"pdf-data")
        archive.writestr("__MACOSX/._holiday.jpg", b"metadata")

    response = client.post(
        "/clipboard/bundle?token=shared-token",
        data=archive_data.getvalue(),
        content_type="application/zip",
        headers={"X-Clipboard-Filename": "Shortcut Input.zip"},
    )
    assert response.status_code == 200
    saved = response.get_json()
    assert saved["type"] == "bundle"
    assert saved["file_count"] == 2

    metadata = client.get("/clipboard/latest/meta?token=shared-token").get_json()
    assert metadata["id"] == saved["id"]
    assert metadata["type"] == "bundle"
    assert [item["filename"] for item in metadata["files"]] == ["holiday.jpg", "report.pdf"]
    assert "data" not in metadata
    assert client.post(
        "/clipboard/bundle?token=shared-token",
        data=b"not a zip",
        content_type="application/zip",
    ).status_code == 400

    oversized = io.BytesIO()
    with zipfile.ZipFile(oversized, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("too-large.bin", b"0" * (1024 * 1024 + 1))
    rejected = client.post(
        "/clipboard/bundle?token=shared-token",
        data=oversized.getvalue(),
        content_type="application/zip",
    )
    assert rejected.status_code == 400
    assert "upload limit" in rejected.get_json()["error"]


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


def test_account_can_delete_only_its_own_history_item(server):
    client = server.app.test_client()
    alice_auth = "?user=alice&password=p%26ss%3Fword"
    bob_headers = {
        "X-Clipboard-User": "bob",
        "X-Clipboard-Password": "second",
    }

    alice_item = client.post(
        "/clipboard" + alice_auth,
        data="delete me",
        content_type="text/plain",
    ).get_json()
    bob_item = client.post(
        "/clipboard",
        data="keep me",
        content_type="text/plain",
        headers=bob_headers,
    ).get_json()

    unauthorized = client.delete(
        f"/clipboard/item/{alice_item['id']}?user=alice&password=wrong",
    )
    assert unauthorized.status_code == 401

    deleted = client.delete(f"/clipboard/item/{alice_item['id']}" + alice_auth)
    assert deleted.status_code == 200
    assert deleted.get_json()["status"] == "deleted"

    assert client.get(f"/clipboard/item/{alice_item['id']}" + alice_auth).status_code == 404
    assert client.get(
        f"/clipboard/item/{bob_item['id']}",
        headers=bob_headers,
    ).status_code == 200


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
        ("automation.shortcut", "application/octet-stream", b"AEA1\x00signed-shortcut-data"),
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
        if filename.endswith(".shortcut"):
            assert latest.headers["Content-Disposition"].startswith("attachment;")


def test_raw_iphone_upload_can_preserve_an_unusual_filename_in_the_url(server):
    client = server.app.test_client()
    payload = b"AEA1\x00binary-shortcut"

    response = client.post(
        "/clipboard?token=shared-token&filename=Morning%20Automation.shortcut",
        data=payload,
        content_type="application/octet-stream",
    )

    assert response.status_code == 200
    latest = client.get("/clipboard/latest/raw?token=shared-token")
    assert latest.data == payload
    assert latest.headers["X-Clipboard-Filename"] == "Morning%20Automation.shortcut"
    assert latest.headers["Content-Disposition"].startswith("attachment;")


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
    assert response.get_json()["version"] == "1.0.4"
