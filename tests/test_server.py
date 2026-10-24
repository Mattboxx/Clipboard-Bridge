import base64
import importlib.util
import io
import json
import os
import socket
import sys
import uuid
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from string import Formatter
from urllib.parse import urlsplit

import pytest
from flask.testing import FlaskClient


SERVER_FILE = Path(__file__).resolve().parents[1] / "clipboard_bridge-Server.py"


@pytest.mark.parametrize("lang", ["en", "it", "es", "fr", "de", "pt", "zh"])
def test_support_link_is_localized_and_does_not_leak_account_credentials(server, lang):
    class Links(HTMLParser):
        support = []
        def handle_starttag(self, tag, attributes):
            attrs = dict(attributes)
            if tag == "a" and attrs.get("class") == "support-link":
                self.support.append(attrs)

    response = server.app.test_client().get("/", query_string={
        "user": "alice", "password": "p&ss?word", "lang": lang})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    parser = Links()
    parser.feed(html)
    assert len(parser.support) == 1
    assert parser.support[0]["href"] == "https://ko-fi.com/mattboxx"
    assert set(parser.support[0]["rel"].split()) == {"noopener", "noreferrer"}
    assert server.WEB_STRINGS[lang]["support_note"] in html
    assert server.WEB_STRINGS[lang]["support"] in html


def test_web_translations_have_complete_keys_and_matching_placeholders(server):
    assert set(server.WEB_STRINGS) == set(server.WEB_LANGUAGES)
    english = server.WEB_STRINGS["en"]
    formatter = Formatter()
    for strings in server.WEB_STRINGS.values():
        assert strings.keys() == english.keys()
        for key, value in strings.items():
            assert isinstance(value, str) and value.strip()
            fields = lambda text: {field for _, field, _, _ in formatter.parse(text) if field is not None}
            assert fields(value) == fields(english[key]), key


@pytest.mark.parametrize("lang", ["en", "it", "es", "fr", "de", "pt", "zh"])
def test_localized_device_guide_login_and_external_links(server, lang):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []

        def handle_starttag(self, tag, attributes):
            if tag == "a":
                self.links.append(dict(attributes))

    client = server.app.test_client()
    strings = server.WEB_STRINGS[lang]
    login = client.get("/", query_string={"lang": lang}, follow_redirects=True)
    assert login.status_code == 200
    assert f'<html lang="{lang}">' in login.text
    assert strings["username"] in login.text and strings["password"] in login.text
    failed = client.post("/login", data={"username": "alice", "password": "bad"})
    assert strings["login_error"] in failed.text
    page = client.post("/login", data={"username": "alice", "password": "p&ss?word"}, follow_redirects=True)
    assert page.status_code == 200
    assert f'<html lang="{lang}">' in page.text
    for key in ("connect", "windows_1", "android_2", "apple_3", "container_3"):
        assert strings[key] in page.text
    assert 'id="connect"' in page.text
    assert 'action="/"' in page.text and 'name="lang"' in page.text
    parser = Links()
    parser.feed(page.text)
    public = [link for link in parser.links if urlsplit(link.get("href", "")).scheme == "https"]
    assert any(link["href"] == server.PROJECT_SITE for link in public)
    for link in public:
        assert urlsplit(link["href"]).hostname in {"mattboxx.github.io", "ko-fi.com"}
        assert not urlsplit(link["href"]).query
        assert "alice" not in link["href"] and "password" not in link["href"]
        assert set(link["rel"].split()) == {"noopener", "noreferrer"}
    logged_out = client.get("/logout", follow_redirects=True)
    assert f'<html lang="{lang}">' in logged_out.text
    assert strings["username"] in logged_out.text
    with client.session_transaction() as preferences:
        assert preferences.permanent and preferences["lang"] == lang
        assert "acct" not in preferences and "auth" not in preferences


@pytest.mark.parametrize("requested,expected", [("pt-BR", "pt"), ("es_ES", "es"),
                                              ("zh-Hans", "zh"), ("FR", "fr"), ("unknown", "en")])
def test_language_aliases_and_default(server, requested, expected):
    client = server.app.test_client()
    response = client.get("/login", query_string={"lang": requested})
    assert f'<html lang="{expected}">' in response.text
    assert f'<html lang="{expected}">' in client.get("/login").text


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
    class BufferedClient(FlaskClient):
        def open(self, *args, **kwargs):
            kwargs.setdefault("buffered", True)
            return super().open(*args, **kwargs)
    module.app.test_client_class = BufferedClient
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


def test_history_search_pagination_and_account_isolation(server):
    server.MAX_HISTORY = 50
    client = server.app.test_client()
    token = "?token=shared-token"
    for value in ("alpha", "report uno", "report due", "report tre"):
        client.post("/clipboard" + token, data=value, content_type="text/plain")
    client.post("/clipboard?user=bob&password=second", data="report private", content_type="text/plain")
    page = client.get("/clipboard/history" + token + "&q=REPORT&type=text&limit=2").get_json()
    assert [entry["preview"] for entry in page["items"]] == ["report tre", "report due"]
    assert page["total"] == 3 and page["count"] == 2 and page["has_more"]
    next_page = client.get("/clipboard/history" + token + "&q=report&limit=2&offset=2").get_json()
    assert [entry["preview"] for entry in next_page["items"]] == ["report uno"]
    assert not next_page["has_more"]
    assert next_page["offset"] == 2
    assert client.get("/clipboard/history" + token).get_json()["count"] == 4


def test_history_searches_all_bundle_filenames(server):
    client = server.app.test_client()
    response = client.post("/clipboard?token=shared-token", data={
        "files": [(io.BytesIO(b"one"), "first.pdf"), (io.BytesIO(b"two"), "second.pdf"),
                  (io.BytesIO(b"three"), "third.pdf"), (io.BytesIO(b"four"), "Caffè.shortcut")],
    }, content_type="multipart/form-data")
    page = client.get("/clipboard/history?token=shared-token&q=caff%C3%A8&type=bundle").get_json()
    assert [entry["id"] for entry in page["items"]] == [response.get_json()["id"]]


@pytest.mark.parametrize("query", ["limit=-1", "limit=0", "limit=1001", "offset=-1", "limit=nope", "type=bad", "q=" + "x" * 201])
def test_invalid_history_parameters_are_rejected(server, query):
    assert server.app.test_client().get("/clipboard/history?token=shared-token&" + query).status_code == 400


def test_web_history_search_and_next_page(server):
    server.MAX_HISTORY = 30
    client = server.app.test_client()
    client.post("/login", data={"password": "shared-web-password"})
    for index in range(25):
        client.post("/clipboard", data=f"report {index}", content_type="text/plain")
    page = client.get("/?q=report&type=text").get_data(as_text=True)
    assert 'id="history"' in page and "25 results" in page
    assert 'offset=20' in page and ">Next</a>" in page
    page = client.get("/?q=report&type=text&offset=20&lang=it").get_data(as_text=True)
    assert "25 risultati" in page and ">Precedenti</a>" in page
    assert "report 0" in page


@pytest.mark.parametrize("action", ["upload", "clear"])
def test_failed_index_commit_keeps_existing_files(server, monkeypatch, action):
    server.MAX_HISTORY = 1
    client = server.app.test_client()
    client.post("/clipboard?token=shared-token", json="keep me")
    before = set((Path(server.DATA_DIR) / "items").iterdir())

    def fail_save(index):
        raise OSError("disk full")

    monkeypatch.setattr(server, "_save_index", fail_save)
    with pytest.raises(OSError):
        if action == "upload":
            client.post("/clipboard?token=shared-token", json="new item")
        else:
            client.delete("/clipboard/history?token=shared-token")
    assert set((Path(server.DATA_DIR) / "items").iterdir()) == before
    assert client.get("/clipboard/latest/raw?token=shared-token").data == b"keep me"


def test_partial_item_write_is_removed(server, monkeypatch):
    real_open = open

    class FailingWriter:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def write(self, payload):
            self.stream.write(payload[:1])
            raise OSError("disk full")

    def failing_open(path, mode="r", *args, **kwargs):
        stream = real_open(path, mode, *args, **kwargs)
        return FailingWriter(stream) if mode == "wb" else stream

    monkeypatch.setattr(server, "open", failing_open, raising=False)
    with server.app.test_request_context():
        with pytest.raises(OSError):
            server._add_binary(b"payload", "file.pdf")
    assert list((Path(server.DATA_DIR) / "items").iterdir()) == []


@pytest.mark.parametrize("method,route", [
    ("get", "/clipboard/history"), ("get", "/clipboard/latest"),
    ("post", "/clipboard"), ("delete", "/clipboard/history"),
])
@pytest.mark.parametrize("damaged", [b'{"unfinished":', b'{}', b'[null]', b'\xff'])
def test_damaged_index_is_not_treated_as_empty_or_overwritten(server, method, route, damaged):
    client = server.app.test_client()
    client.post("/clipboard?token=shared-token", json="original item")
    index = Path(server.INDEX_FILE)
    index.write_bytes(damaged)
    before = {path.name: path.read_bytes() for path in Path(server.ITEMS_DIR).iterdir()}
    response = getattr(client, method)(route + "?token=shared-token", json="new item"
                                     if method == "post" else None)
    assert response.status_code == 503
    assert response.get_json()["code"] == "history_unavailable"
    assert index.read_bytes() == damaged
    assert {path.name: path.read_bytes() for path in Path(server.ITEMS_DIR).iterdir()} == before


def test_damaged_account_does_not_affect_other_spaces_and_can_be_restored(server, caplog):
    client = server.app.test_client()
    shared = "?token=shared-token"
    alice = "?user=alice&password=p%26ss%3Fword"
    bob = "?user=bob&password=second"
    for auth, text in ((shared, "general"), (alice, "private sample"), (bob, "other account")):
        assert client.post("/clipboard" + auth, json=text).status_code == 200
    path = Path(server.DATA_DIR) / "users/alice/index.json"
    backup = path.read_bytes()
    path.write_bytes(b"{damaged")
    response = client.post("/clipboard" + alice, json="must not erase history")
    assert response.status_code == 503
    assert client.get("/clipboard/latest/raw" + shared).data == b"general"
    assert client.get("/clipboard/latest/raw" + bob).data == b"other account"
    assert client.get("/health").status_code == 200
    assert "private sample" not in caplog.text and "alice" not in caplog.text
    assert str(server.DATA_DIR) not in response.get_data(as_text=True)
    assert "Retry-After" in response.headers
    path.write_bytes(backup)
    assert client.get("/clipboard/latest/raw" + alice).data == b"private sample"


def test_health_reports_unavailable_instead_of_empty_when_shared_index_is_damaged(server):
    Path(server.INDEX_FILE).write_bytes(b"{damaged")
    response = server.app.test_client().get("/health")
    assert response.status_code == 503
    assert response.get_json()["code"] == "history_unavailable"


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


@pytest.mark.parametrize("other", ["Demo", "demo."])
def test_account_names_never_share_a_physical_history_directory(server, monkeypatch, other):
    accounts = {"demo": "lower", other: "upper", "bob": "second"}
    monkeypatch.setattr(server, "ACCOUNTS", accounts)
    monkeypatch.setattr(server, "_ACCOUNT_ALIASES", server._account_alias_groups(accounts))
    lower = Path(server.DATA_DIR) / "users/demo"
    upper = lower.parent / other
    (lower / "items").mkdir(parents=True)
    (lower / "items/legacy.txt").write_text("legacy sample", encoding="utf-8")
    legacy = json.dumps([{"id": "legacy", "type": "text", "file": "legacy.txt", "preview": "legacy sample"}]).encode()
    (lower / "index.json").write_bytes(legacy)
    aliased = upper.exists() and os.path.samefile(lower, upper)
    client = server.app.test_client()
    first = client.post("/clipboard", query_string={"user": "demo", "password": "lower"}, json="lower space")
    second = client.post("/clipboard", query_string={"user": other, "password": "upper"}, json="upper space")
    if aliased:
        assert first.status_code == second.status_code == 503
        assert first.get_json()["code"] == second.get_json()["code"] == "account_storage_conflict"
        assert (lower / "index.json").read_bytes() == legacy
        assert list((lower / "items").iterdir()) == [lower / "items/legacy.txt"]
    else:
        assert first.status_code == second.status_code == 200
        assert client.get("/clipboard/latest/raw", query_string={"user": "demo", "password": "lower"}).data == b"lower space"
        assert client.get("/clipboard/latest/raw", query_string={"user": other, "password": "upper"}).data == b"upper space"
    assert client.get("/health").status_code == 200
    assert client.post("/clipboard?token=shared-token", json="general space").status_code == 200
    assert client.get("/clipboard/latest/raw?token=shared-token").data == b"general space"


@pytest.mark.parametrize("method,route", [
    ("get", "/clipboard/latest/raw"), ("get", "/clipboard/history"),
    ("post", "/clipboard"), ("delete", "/clipboard/history"),
])
def test_filesystem_alias_fails_closed_without_leaking_data_or_paths(server, monkeypatch, method, route, caplog):
    accounts = {"alice": "lower", "Alice": "upper", "bob": "second"}
    monkeypatch.setattr(server, "ACCOUNTS", accounts)
    monkeypatch.setattr(server, "_ACCOUNT_ALIASES", server._account_alias_groups(accounts))
    monkeypatch.setattr(server.os.path, "samefile", lambda first, second: True)
    client = server.app.test_client()
    response = getattr(client, method)(route, query_string={"user": "Alice", "password": "upper"},
                                       data=b"new data" if method == "post" else None)
    assert response.status_code == 503
    assert response.get_json()["code"] == "account_storage_conflict"
    assert str(server.DATA_DIR) not in response.get_data(as_text=True)
    assert "Alice" not in caplog.text and "upper" not in caplog.text
    assert client.post("/clipboard?user=bob&password=second", json="healthy account").status_code == 200


def test_account_directory_permission_failure_has_a_safe_response(server, monkeypatch):
    original = server.os.makedirs

    def denied(path, *args, **kwargs):
        if "users" in Path(path).parts:
            raise PermissionError("private path and diagnostic details")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(server.os, "makedirs", denied)
    response = server.app.test_client().get("/clipboard/history?user=alice&password=p%26ss%3Fword")
    assert response.status_code == 503
    assert response.get_json()["code"] == "account_storage_unavailable"
    assert "private path" not in response.get_data(as_text=True)


def test_alias_guard_keeps_large_account_sets_without_per_request_directory_scans(server, monkeypatch):
    accounts = server._parse_accounts("\n".join(f"user{number}:sample" for number in range(10000)))
    assert len(accounts) == 10000
    monkeypatch.setattr(server, "ACCOUNTS", accounts)
    monkeypatch.setattr(server, "_ACCOUNT_ALIASES", server._account_alias_groups(accounts))
    scans = []
    monkeypatch.setattr(server.os.path, "samefile", lambda *paths: scans.append(paths) or False)
    client = server.app.test_client()
    assert client.post("/clipboard?user=user9999&password=sample", json="many accounts").status_code == 200
    assert client.get("/clipboard/latest/raw?user=user9999&password=sample").data == b"many accounts"
    assert scans == []


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


@pytest.mark.parametrize("text", [
    "https://www.reddit.com/r/example/comments/demo/title/?x=1&y=%23value#section",
    "https://example.com/?q=caff\u00e8\U0001f600&literal=%26%3D",
    "Read this: https://example.com/one\nhttps://example.org/two",
])
def test_apple_json_link_is_text_without_fetching_the_page(server, monkeypatch, text):
    def reject_connect(*args, **kwargs):
        pytest.fail("Storing clipboard text must not connect to a shared URL")

    monkeypatch.setattr(socket.socket, "connect", reject_connect)
    client = server.app.test_client()
    query = {"user": "alice", "password": "p&ss?word"}
    response = client.post("/clipboard", query_string=query, json={"text": text})
    assert response.status_code == 200
    assert response.get_json()["type"] == "text"
    item = client.get("/clipboard/latest", query_string=query).get_json()
    assert item["text"] == text and item["mime"] == "text/plain"
    received = client.get("/clipboard/latest/raw", query_string=query)
    assert received.data == text.encode("utf-8")
    assert received.content_type == "text/plain; charset=utf-8"
    assert client.get("/clipboard/latest/raw?token=shared-token").data == b""
    assert client.get("/clipboard/history?token=shared-token").get_json()["items"] == []


def test_shared_html_document_keeps_original_bytes(server):
    client = server.app.test_client()
    raw = b'<!DOCTYPE html><html><body><a href="https://example.com/">Link</a></body></html>'
    route = "/clipboard?token=shared-token&filename=page.html"
    response = client.post(route, data=raw, content_type="text/html; charset=utf-8")
    assert response.status_code == 200
    assert response.get_json()["type"] == "file"
    received = client.get("/clipboard/latest/raw?token=shared-token")
    assert received.data == raw
    assert "page.html" in received.headers["Content-Disposition"]


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
    assert response.get_json()["version"] == "1.0.10"


def test_web_session_duration_is_configurable(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIPBOARD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CLIPBOARD_SESSION_DAYS", "90")
    spec = importlib.util.spec_from_file_location("session_duration_test", SERVER_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.app.permanent_session_lifetime.days == 90


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
def test_unicode_text_and_line_endings_round_trip_exactly(server, encoding):
    client = server.app.test_client()
    text = "A\r\nB\rC\n\t  \u96ea\U0001f600\x00"
    saved = client.post("/clipboard?token=shared-token", data=text.encode(encoding),
                        content_type="text/plain")
    assert saved.status_code == 200
    assert client.get("/clipboard/latest/raw?token=shared-token").data == text.encode("utf-8")
    assert client.get("/clipboard/latest?token=shared-token").get_json()["text"] == text


@pytest.mark.parametrize("route,mime", [
    ("/clipboard", "text/rtf"), ("/clipboard", "application/rtf"),
    ("/clipboard", "application/x-rtf"), ("/clipboard/text", "text/plain"),
])
@pytest.mark.parametrize("encoding", ["ascii", "utf-16", "utf-32"])
def test_rtf_clipboard_is_plain_unicode_in_every_read_endpoint(server, route, mime, encoding):
    client = server.app.test_client()
    auth = "?user=alice&password=p%26ss%3Fword"
    rtf = rb"{\rtf1\ansi\ansicpg1252 Caff\'e8 \b bold\b0  \u-10179?\u-8704?\par\tab fine}"
    expected = "Caff\u00e8 bold \U0001f600\n\tfine"
    saved = client.post(route + auth, data=rtf.decode("ascii").encode(encoding), content_type=mime)
    assert saved.status_code == 200
    item_id = saved.get_json()["id"]
    for path in ("/clipboard/latest", f"/clipboard/item/{item_id}"):
        item = client.get(path + auth).get_json()
        assert item["type"] == "text" and item["mime"] == "text/plain"
        assert item["text"] == expected
        assert item["size"] == len(expected.encode("utf-8"))
    for path in ("/clipboard/latest/raw", f"/clipboard/item/{item_id}/raw", "/clipboard/text/raw"):
        received = client.get(path + auth)
        assert received.data == expected.encode("utf-8")
        assert received.content_type == "text/plain; charset=utf-8"
    assert client.get("/clipboard/history" + auth).get_json()["items"][0]["preview"] == expected
    assert client.get("/clipboard/latest?token=shared-token").get_json()["type"] == "empty"


@pytest.mark.parametrize("mode", ["named", "multipart", "explicit", "group"])
def test_rtf_documents_are_files_not_clipboard_text(server, mode):
    client = server.app.test_client()
    raw = rb"{\rtf1\ansi Original \b document\b0 \u-10179?\u-8704?}"
    auth = "?token=shared-token"
    if mode == "named":
        saved = client.post("/clipboard" + auth + "&filename=notes.rtf", data=raw, content_type="text/rtf")
    elif mode in ("multipart", "group"):
        files = [(io.BytesIO(raw), "notes.rtf")]
        if mode == "group":
            files.append((io.BytesIO(b"pdf"), "other.pdf"))
        saved = client.post("/clipboard" + auth, data={"files": files}, content_type="multipart/form-data")
    else:
        saved = client.post("/clipboard/file" + auth, data=raw, content_type="application/rtf")
    assert saved.status_code == 200
    item = client.get("/clipboard/latest" + auth).get_json()
    assert item["type"] == ("bundle" if mode == "group" else "file")
    path = f"/clipboard/item/{item['id']}/file/0/raw" if mode == "group" else "/clipboard/latest/raw"
    assert client.get(path + auth).data == raw


def test_unicode_password_and_token_are_supported(server):
    server.ACCOUNTS["unicode"] = "caff\u00e8-\u96ea-\U0001f511"
    server._ACCOUNT_ALIASES = server._account_alias_groups(server.ACCOUNTS)
    server.AUTH_TOKEN = "tok\u00e9n-\u96ea"
    client = server.app.test_client()
    assert client.post("/clipboard", query_string={"user": "unicode", "password": server.ACCOUNTS["unicode"]},
                       json="private").status_code == 200
    assert client.get("/clipboard/history", query_string={"token": server.AUTH_TOKEN}).status_code == 200
    assert client.get("/clipboard/history", query_string={"user": "unicode", "password": "wrong\u96ea"}).status_code == 401


def test_url_filename_is_not_decoded_twice(server):
    client = server.app.test_client()
    response = client.post("/clipboard", query_string={"token": "shared-token", "filename": "literal%20name.shortcut"},
                           data=b"test", content_type="application/octet-stream")
    assert response.status_code == 200
    latest = client.get("/clipboard/latest?token=shared-token").get_json()
    assert latest["filename"] == "literal%20name.shortcut"


@pytest.mark.parametrize("route", ["/clipboard", "/clipboard/text"])
def test_malformed_json_does_not_replace_the_clipboard(server, route):
    client = server.app.test_client()
    client.post("/clipboard?token=shared-token", json="keep me")
    response = client.post(route + "?token=shared-token", data=b"{not JSON", content_type="application/json")
    assert response.status_code == 400
    assert client.get("/clipboard/latest/raw?token=shared-token").data == b"keep me"


def test_large_group_duplicate_names_and_zero_byte_members(server):
    client = server.app.test_client()
    uploads = [(io.BytesIO(bytes([n]) * n), "same.shortcut") for n in range(30)]
    response = client.post("/clipboard?token=shared-token", data={"files": uploads})
    assert response.status_code == 200
    item_id = response.get_json()["id"]
    history = client.get("/clipboard/history?token=shared-token").get_json()["items"]
    assert len(history) == 1
    assert history[0]["file_count"] == 30
    for index in (0, 1, 29):
        assert client.get(f"/clipboard/item/{item_id}/file/{index}/raw?token=shared-token").data == bytes([index]) * index
    with zipfile.ZipFile(io.BytesIO(client.get("/clipboard/latest/raw?token=shared-token").data)) as zipped:
        assert len(set(zipped.namelist())) == 30
        assert zipped.read(zipped.namelist()[29]) == bytes([29]) * 29


def test_concurrent_uploads_preserve_every_history_entry(server):
    from concurrent.futures import ThreadPoolExecutor
    server.MAX_HISTORY = 100
    def post(number):
        with server.app.test_client() as client:
            response = client.post("/clipboard?token=shared-token", json={"text": str(number)})
            assert response.status_code == 200
            return response.get_json()["id"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = set(pool.map(post, range(32)))
    history = server.app.test_client().get("/clipboard/history?token=shared-token").get_json()["items"]
    assert {item["id"] for item in history} == ids


def test_readers_and_history_trimming_do_not_race_deleted_files(server):
    from concurrent.futures import ThreadPoolExecutor
    server.MAX_HISTORY = 1
    def exercise(number):
        with server.app.test_client() as client:
            saved = client.post("/clipboard?token=shared-token", data=bytes([number]),
                                content_type="application/octet-stream").get_json()
            for route in ("/clipboard/latest", "/clipboard/latest/raw",
                          f"/clipboard/item/{saved['id']}", f"/clipboard/item/{saved['id']}/raw"):
                response = client.get(route + "?token=shared-token")
                assert response.status_code in (200, 404)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(exercise, range(32)))
