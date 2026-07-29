import importlib.util
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
    assert response.get_json()["version"] == "1.0.1"
