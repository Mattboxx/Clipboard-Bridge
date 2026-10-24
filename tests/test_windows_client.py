import base64
import importlib.util
import json
import os
import subprocess
import sys
import threading
import zipfile
import io
import socket
import http.client
import time
import gc
import tkinter
from types import SimpleNamespace
from pathlib import Path

import requests
import pytest


@pytest.fixture(autouse=True)
def collect_gui_resources_on_test_thread():
    yield
    # Destroyed Tk windows can leave cycles; release them before HTTP workers run.
    gc.collect()


@pytest.fixture(scope="session")
def tk_test_root():
    # Match the app: one Tk interpreter, separate Toplevel windows for each view.
    root = tkinter.Tk()
    root.withdraw()
    yield root
    root.destroy()
    gc.collect()


@pytest.fixture()
def embedded(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    server = client.http.server.ThreadingHTTPServer(("127.0.0.1", 0), client._SrvHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield client, server.server_address
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_queued_file_send_cannot_move_to_a_different_account(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    queued, uploads, notices = [], [], []
    monkeypatch.setattr(client.filedialog, "askopenfilenames", lambda **_: ("example.pdf",))
    monkeypatch.setattr(client, "_run_bg", queued.append)
    monkeypatch.setattr(client, "push_files", uploads.append)
    monkeypatch.setattr(client, "notify", notices.append)
    client.action_send_file()
    client._apply_config(dict(client.config, username="different-account"))
    queued.pop()()
    assert uploads == []
    assert len(notices) == 1 and client.t("remote_changed") in notices[0]


@pytest.mark.parametrize("text", [
    "https://www.reddit.com/r/example/comments/demo/title/?x=1&y=%23value#section",
    "https://example.com/?q=caff\u00e8\U0001f600&literal=%26%3D",
    "Read this: https://example.com/one\nhttps://example.org/two",
])
def test_embedded_apple_json_link_is_text_without_fetching_the_page(embedded, monkeypatch, text):
    client, address = embedded
    base = f"http://{address[0]}:{address[1]}"
    connect = socket.socket.connect

    def loopback_only(connection, destination):
        assert destination == address, "Storing clipboard text must not connect to a shared URL"
        return connect(connection, destination)

    monkeypatch.setattr(socket.socket, "connect", loopback_only)
    response = requests.post(base + "/clipboard", json={"text": text}, timeout=5)
    assert response.status_code == 200
    assert response.json()["type"] == "text"
    item = requests.get(base + "/clipboard/latest", timeout=5).json()
    assert item["text"] == text and item["mime"] == "text/plain"
    received = requests.get(base + "/clipboard/latest/raw", timeout=5)
    assert received.content == text.encode("utf-8")
    assert received.headers["Content-Type"] == "text/plain; charset=utf-8"


def test_embedded_shared_html_document_keeps_original_bytes(embedded):
    client, address = embedded
    base = f"http://{address[0]}:{address[1]}"
    raw = b'<!DOCTYPE html><html><body><a href="https://example.com/">Link</a></body></html>'
    response = requests.post(base + "/clipboard?filename=page.html", data=raw,
                             headers={"Content-Type": "text/html; charset=utf-8"}, timeout=5)
    assert response.status_code == 200
    assert response.json()["type"] == "file"
    received = requests.get(base + "/clipboard/latest/raw", timeout=5)
    assert received.content == raw
    assert "page.html" in received.headers["Content-Disposition"]


def test_x64_installer_samples_match_actual_client_data_paths(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/windows-x64.yml").read_text(encoding="utf-8")
    for path in (client.CONFIG_FILE, client.LOCAL_INDEX, client.HOST_INDEX):
        relative = Path(path).relative_to(client.DATA_DIR).as_posix()
        assert f"'{relative}' = " in workflow, f"Installer preservation misses {relative}"


def test_embedded_rejects_negative_bundle_member(embedded):
    client, address = embedded
    base = f"http://{address[0]}:{address[1]}"
    entry = client._host_add_bundle([(b"first", "a.bin", None), (b"last", "b.bin", None)])
    response = requests.get(base + f"/clipboard/item/{entry['id']}/file/-1/raw", timeout=5)
    assert response.status_code == 404


@pytest.mark.parametrize("headers,body", [
    (b"Content-Length: -1\r\n", b""),
    (b"Content-Length: nope\r\n", b""),
    (b"Content-Length: 10\r\n", b"short"),
    (b"Content-Length: 3\r\nContent-Length: 3\r\n", b"abc"),
])
def test_embedded_rejects_invalid_or_incomplete_body(embedded, headers, body):
    client, address = embedded
    with socket.create_connection(address, timeout=5) as connection:
        connection.sendall(b"POST /clipboard/text HTTP/1.0\r\nHost: localhost\r\n"
                           + headers + b"Content-Type: text/plain\r\n\r\n" + body)
        connection.shutdown(socket.SHUT_WR)
        response = http.client.HTTPResponse(connection)
        response.begin()
        assert response.status == 400
        response.read()
    assert client._host_load() == []


@pytest.mark.parametrize("mime", ["text/rtf", "application/rtf", "application/x-rtf"])
@pytest.mark.parametrize("encoding", ["ascii", "utf-16", "utf-32"])
def test_embedded_converts_rtf_clipboard_to_plain_unicode(embedded, mime, encoding):
    client, address = embedded
    base = f"http://{address[0]}:{address[1]}"
    raw = rb"{\rtf1\ansi Caff\'e8 \u-10179?\u-8704?\par\tab fine}"
    expected = "Caff\u00e8 \U0001f600\n\tfine"
    saved = requests.post(base + "/clipboard", data=raw.decode("ascii").encode(encoding),
                          headers={"Content-Type": mime}, timeout=5)
    assert saved.status_code == 200
    assert saved.json()["type"] == "text"
    item_id = saved.json()["id"]
    item = requests.get(base + "/clipboard/latest", timeout=5).json()
    assert item["text"] == expected and item["mime"] == "text/plain"
    assert item["size"] == len(expected.encode("utf-8"))
    for path in ("/clipboard/latest/raw", f"/clipboard/item/{item_id}/raw"):
        received = requests.get(base + path, timeout=5)
        assert received.content == expected.encode("utf-8")
        assert received.headers["Content-Type"] == "text/plain; charset=utf-8"
    assert requests.get(base + "/clipboard/history", timeout=5).json()["items"][0]["preview"] == expected


@pytest.mark.parametrize("mode", ["named", "multipart", "explicit", "group"])
def test_embedded_keeps_rtf_documents_unchanged(embedded, mode):
    client, address = embedded
    base = f"http://{address[0]}:{address[1]}"
    raw = rb"{\rtf1\ansi Original \b document\b0 \u-10179?\u-8704?}"
    if mode == "named":
        saved = requests.post(base + "/clipboard?filename=notes.rtf", data=raw,
                              headers={"Content-Type": "text/rtf"}, timeout=5)
    elif mode in ("multipart", "group"):
        parts = [("files", ("notes.rtf", raw, "application/rtf"))]
        if mode == "group":
            parts.append(("files", ("other.pdf", b"pdf", "application/pdf")))
        saved = requests.post(base + "/clipboard", files=parts, timeout=5)
    else:
        saved = requests.post(base + "/clipboard/file", data=raw,
                              headers={"Content-Type": "application/rtf"}, timeout=5)
    assert saved.status_code == 200
    item = requests.get(base + "/clipboard/latest", timeout=5).json()
    assert item["type"] == ("bundle" if mode == "group" else "file")
    path = f"/clipboard/item/{item['id']}/file/0/raw" if mode == "group" else "/clipboard/latest/raw"
    assert requests.get(base + path, timeout=5).content == raw


def test_windows_converts_text_on_send_and_receive_without_echo(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    rtf = r"{\rtf1\ansi Caff\'e8 \u-10179?\u-8704?}"
    expected = "Caff\u00e8 \U0001f600"
    sent, copied = [], []
    def post(url, **kwargs):
        sent.append(kwargs["json"]["text"])
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"id": "sent"})
    monkeypatch.setattr(client.requests, "post", post)
    monkeypatch.setattr(client.pyperclip, "paste", lambda: expected)
    monkeypatch.setattr(client.pyperclip, "copy", copied.append)
    monkeypatch.setattr(client, "_get_clipboard_rtf", lambda: pytest.fail("Unicode is preferred"))
    assert client.get_clipboard_text() == expected
    client.push_text(rtf)
    assert sent == [expected]
    client._take_local_upload_marker()
    client._copy_remote_item({"id": "received", "type": "text", "text": rtf})
    assert copied == [expected]
    assert client._take_local_upload_marker() == ("text", expected)


@pytest.mark.parametrize("unicode_available", [False, True])
def test_windows_reads_rtf_only_when_unicode_format_is_missing(tmp_path, monkeypatch, unicode_available):
    client = load_client(tmp_path, monkeypatch)
    raw = rb"{\rtf1\ansi Caff\'e8 \u-10179?\u-8704?}"
    buffer = client.ctypes.create_string_buffer(raw)
    closed, unlocked = [], []
    user32 = SimpleNamespace(
        OpenClipboard=lambda handle: True,
        CloseClipboard=lambda: closed.append(True),
        IsClipboardFormatAvailable=lambda fmt: unicode_available if fmt == 13 else True,
        RegisterClipboardFormatW=lambda name: 0xC000,
        GetClipboardData=lambda fmt: 123,
    )
    kernel32 = SimpleNamespace(
        GlobalSize=lambda handle: len(buffer),
        GlobalLock=lambda handle: client.ctypes.addressof(buffer),
        GlobalUnlock=lambda handle: unlocked.append(handle),
    )
    monkeypatch.setattr(client.ctypes, "WinDLL", lambda name, **kw: user32 if name == "user32" else kernel32)
    monkeypatch.setattr(client.pyperclip, "paste", lambda: "")
    assert client.get_clipboard_text() == ("" if unicode_available else "Caff\u00e8 \U0001f600")
    assert closed == [True]
    assert unlocked == ([] if unicode_available else [123])


def test_missing_file_does_not_upload_a_partial_group(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    present = tmp_path / "present.pdf"
    present.write_bytes(b"pdf")
    monkeypatch.setattr(client.requests, "post", lambda *a, **kw: pytest.fail("Partial upload"))
    with pytest.raises((ValueError, FileNotFoundError)):
        client.push_files([str(present), str(tmp_path / "missing.pdf")])


def test_auto_sync_resends_text_after_clipboard_was_cleared(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    sent = []

    class Iterations:
        step = 0

        def is_set(self):
            return self.step == 3

        def wait(self, timeout):
            self.step += 1

    iterations = Iterations()
    client.config.update(auto_sync=True, auto_receive_files=False)
    monkeypatch.setattr(client, "stop_event", iterations)
    monkeypatch.setattr(client, "check_connection", lambda *args, **kwargs: True)
    monkeypatch.setattr(client, "_clipboard_sequence", lambda: iterations.step)
    monkeypatch.setattr(client, "get_clipboard_files", lambda: [])
    monkeypatch.setattr(client, "get_clipboard_image", lambda: None)
    monkeypatch.setattr(client, "get_clipboard_text", lambda: ["hello", "", "hello"][iterations.step])
    monkeypatch.setattr(client, "poll_latest", lambda known: {})
    monkeypatch.setattr(client, "push_text", lambda value: sent.append(value))
    client.sync_loop()
    assert sent == ["hello", "hello"]


def test_embedded_history_has_search_filters_and_pages(embedded):
    client, address = embedded
    base = f"http://{address[0]}:{address[1]}"
    for value in ("other", "Report one", "Report two", "Report three"):
        client._host_add("text", value)
    page = requests.get(base + "/clipboard/history", params={"q": "REPORT", "type": "text", "limit": 2}, timeout=5).json()
    assert page["total"] == 3 and page["has_more"]
    assert [entry["preview"] for entry in page["items"]] == ["Report three", "Report two"]
    response = requests.get(base + "/clipboard/history?offset=-1", timeout=5)
    assert response.status_code == 400
    assert requests.delete(base + "/clipboard/item/missing", timeout=5).status_code == 404
    item_id = client._host_load()[0]["id"]
    assert requests.delete(base + f"/clipboard/item/{item_id}/raw", timeout=5).status_code == 404
    assert requests.get(base + f"/clipboard/item/{item_id}", timeout=5).status_code == 200


def test_client_requests_history_page_in_the_selected_account(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(username="alice", password="private")
    captured = []

    def get(url, **kwargs):
        captured.append(kwargs["params"])
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"items": [], "total": 0})

    monkeypatch.setattr(client.requests, "get", get)
    assert client.fetch_history_page(30, "report", "file", 60)["total"] == 0
    assert captured == [{"limit": 30, "q": "report", "type": "file", "offset": 60,
                         "user": "alice", "password": "private"}]
    bundle = {"type": "bundle", "preview": "first", "paths": ["other.pdf", "report.pdf"]}
    assert client._filter_history([bundle], "REPORT", "bundle") == [bundle]


@pytest.mark.parametrize("password", ["caff\u00e8\u96ea", " leading", "line\r\nbreak"])
def test_non_header_credentials_keep_compatible_url_encoding(tmp_path, monkeypatch, password):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(username="alice", password=password, token="ignored")
    assert client.auth_headers() == {"X-Auth-Token": "ignored"}
    assert client.auth_params({"limit": 1}) == {"limit": 1, "user": "alice", "password": password}
    prepared = requests.Request("GET", "http://192.0.2.10/clipboard", params=client.auth_params()).prepare()
    assert "\r" not in prepared.url and "\n" not in prepared.url


def test_crash_log_redacts_url_credentials(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    client._log_crash(requests.HTTPError(
        "GET http://192.0.2.10/clipboard?user=alice&password=private%26value&token=private-token&q=notes"))
    log = Path(client.ERROR_LOG).read_text(encoding="utf-8")
    assert "private" not in log and "alice" not in log
    assert "password=[redacted]" in log and "q=notes" in log


def test_failed_embedded_index_commit_keeps_old_files(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    client.config["max_local_history"] = 1
    client._host_add("text", "keep me")
    before = set(Path(client.HOST_ITEMS).iterdir())

    def fail_save(index):
        raise OSError("disk full")

    monkeypatch.setattr(client, "_host_save", fail_save)
    with pytest.raises(OSError):
        client._host_add_bundle([(b"one", "first.bin", None), (b"two", "second.bin", None)])
    assert set(Path(client.HOST_ITEMS).iterdir()) == before
    assert client._host_with_content(client._host_load()[0])["text"] == "keep me"


@pytest.mark.parametrize("damaged", [b'{"unfinished":', b'{}', b'[null]', b'\xff'])
def test_damaged_windows_host_index_preserves_every_stored_file(embedded, damaged):
    client, address = embedded
    client._host_add("text", "original item")
    Path(client.HOST_INDEX).write_bytes(damaged)
    before = {path.name: path.read_bytes() for path in Path(client.HOST_ITEMS).iterdir()}
    base = f"http://{address[0]}:{address[1]}"
    for method, route in ((requests.get, "/clipboard/history"),
                          (requests.post, "/clipboard"),
                          (requests.delete, "/clipboard/history")):
        response = method(base + route, data=b"new item", headers={"Content-Type": "text/plain"}, timeout=5)
        assert response.status_code == 503
        assert response.json()["code"] == "history_unavailable"
        assert Path(client.HOST_INDEX).read_bytes() == damaged
        assert {path.name: path.read_bytes() for path in Path(client.HOST_ITEMS).iterdir()} == before


@pytest.mark.parametrize("damaged", [b'{"unfinished":', b'{}', b'[null]', b'\xff'])
def test_damaged_local_index_is_not_replaced_by_new_clipboard_text(tmp_path, monkeypatch, damaged):
    client = load_client(tmp_path, monkeypatch)
    Path(client.LOCAL_INDEX).write_bytes(damaged)
    with pytest.raises(client.HistoryStoreError):
        client.record_local_text("new item")
    assert Path(client.LOCAL_INDEX).read_bytes() == damaged


def test_windows_host_recovers_after_restoring_a_valid_index(embedded):
    client, address = embedded
    client._host_add("text", "preserved text")
    index = Path(client.HOST_INDEX)
    backup = index.read_bytes()
    index.write_bytes(b"{damaged")
    base = f"http://{address[0]}:{address[1]}"
    assert requests.get(base + "/health", timeout=5).status_code == 503
    response = requests.post(base + "/clipboard", data=b"new", headers={"Content-Type": "text/plain"}, timeout=5)
    assert response.status_code == 503
    assert str(client.HOST_DIR) not in response.text
    index.write_bytes(backup)
    assert requests.get(base + "/clipboard/latest/raw", timeout=5).content == b"preserved text"
    assert requests.get(base + "/health", timeout=5).status_code == 200


def test_optional_local_history_warns_once_and_does_not_fail_a_successful_send(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    Path(client.LOCAL_INDEX).write_bytes(b"{damaged")
    sent, notices = [], []
    monkeypatch.setattr(client, "notify", lambda message, **kwargs: notices.append(message))
    monkeypatch.setattr(client, "get_clipboard_files", lambda: None)
    monkeypatch.setattr(client, "get_clipboard_image", lambda: None)
    monkeypatch.setattr(client, "get_clipboard_text", lambda: "public sample")
    monkeypatch.setattr(client, "push_text", lambda text: sent.append(text) or "sent")
    client.action_send_clipboard()
    client.action_send_clipboard()
    assert sent == ["public sample", "public sample"]
    assert notices.count(client.t("local_history_error")) == 1
    assert notices.count(client.t("text_sent")) == 2
    assert Path(client.LOCAL_INDEX).read_bytes() == b"{damaged"
    assert "public sample" not in Path(client.ERROR_LOG).read_text(encoding="utf-8")
    Path(client.LOCAL_INDEX).write_text("[]", encoding="utf-8")
    assert client._try_local_history(client.record_local_text, "after recovery")
    assert not client._local_history_warning


def test_auto_sync_continues_with_a_damaged_optional_local_history(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    Path(client.LOCAL_INDEX).write_bytes(b"{damaged")
    client.config.update(auto_sync=True, auto_receive_files=False, monitor_clipboard=True)

    class TwoIterations:
        count = 0
        def is_set(self): return self.count >= 2
        def wait(self, timeout): self.count += 1

    sent, notices = [], []
    monkeypatch.setattr(client, "stop_event", TwoIterations())
    monkeypatch.setattr(client, "check_connection", lambda *args, **kwargs: True)
    monkeypatch.setattr(client, "_clipboard_sequence", lambda: 1)
    monkeypatch.setattr(client, "get_clipboard_files", lambda: None)
    monkeypatch.setattr(client, "get_clipboard_image", lambda: None)
    monkeypatch.setattr(client, "get_clipboard_text", lambda: "public sample")
    monkeypatch.setattr(client, "push_text", lambda text: sent.append(text) or "uploaded")
    monkeypatch.setattr(client, "poll_latest", lambda known: {"type": "empty"})
    monkeypatch.setattr(client, "notify", lambda message, **kwargs: notices.append(message))
    client.sync_loop()
    assert sent == ["public sample"]
    assert notices.count(client.t("local_history_error")) == 1
    assert Path(client.LOCAL_INDEX).read_bytes() == b"{damaged"


@pytest.mark.parametrize("lang", ["en", "it"])
def test_damaged_background_cache_does_not_block_host_history_or_settings(tmp_path, monkeypatch, tk_test_root, lang):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(lang=lang, hotkeys_enabled=False, mode="client")
    index = Path(client.LOCAL_INDEX)
    index.write_bytes(b"{damaged")
    monkeypatch.setattr(client, "_root", tk_test_root)
    monkeypatch.setattr(client, "fetch_history_page", lambda *args: {"items": []})
    monkeypatch.setattr(client, "check_connection", lambda *args, **kwargs: True)
    monkeypatch.setattr(client, "unregister_hotkeys", lambda: None)
    monkeypatch.setattr(client, "notify", lambda *args, **kwargs: None)
    errors = []
    monkeypatch.setattr(tk_test_root, "report_callback_exception", lambda *args: errors.append(args))

    def descendants(parent):
        for child in parent.winfo_children():
            yield child
            yield from descendants(child)

    try:
        client.open_history_window()
        window = next(child for child in tk_test_root.winfo_children()
                      if getattr(child, "_view_name", None) == "history")
        widgets = list(descendants(window))
        assert not any(isinstance(child, client.ttk.Radiobutton)
                       and child.cget("text") == client.t("tab_local") for child in widgets)
        tk_test_root.update()
        window._close_history()
        client.open_settings()
        window = next(child for child in tk_test_root.winfo_children()
                      if getattr(child, "_view_name", None) == "settings")
        save = next(child for child in descendants(window) if isinstance(child, client.ttk.Button)
                    and child.cget("text") == client.t("save"))
        save.invoke()
        tk_test_root.update()
        assert not window.winfo_exists()
        assert json.loads(Path(client.CONFIG_FILE).read_text(encoding="utf-8"))["lang"] == lang
        assert index.read_bytes() == b"{damaged"
        assert not errors
    finally:
        for child in tk_test_root.winfo_children():
            close = getattr(child, "_close_history", None)
            close() if close else child.destroy()


def test_partial_embedded_bundle_is_cleaned_up(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    original = client._host_write_item
    calls = []

    def write(filename, payload):
        calls.append(filename)
        if len(calls) == 2:
            raise OSError("disk full")
        original(filename, payload)

    monkeypatch.setattr(client, "_host_write_item", write)
    with pytest.raises(OSError):
        client._host_add_bundle([(b"one", "a.bin", None), (b"two", "b.bin", None)])
    assert list(Path(client.HOST_ITEMS).iterdir()) == []
    assert client._host_load() == []


def test_failed_local_history_commit_preserves_images(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    client.config["max_local_history"] = 1
    client.record_local_image(client.Image.new("RGB", (2, 2), "red"))
    before = set(Path(client.LOCAL_DIR).glob("*.png"))
    old_index = client._local_load()
    original = client.os.replace

    def replace(source, target):
        if target == client.LOCAL_INDEX:
            raise OSError("disk full")
        original(source, target)

    monkeypatch.setattr(client.os, "replace", replace)
    with pytest.raises(OSError):
        client.record_local_image(client.Image.new("RGB", (2, 2), "blue"))
    assert set(Path(client.LOCAL_DIR).glob("*.png")) == before
    assert client._local_load() == old_index


@pytest.mark.parametrize("saved", [[], {"server_port": -1, "host_port": None,
    "poll_interval": "invalid", "max_local_history": -10, "_legacy_migration_version": "broken",
    "token": None, "auto_sync": "false", "username": "alice", "password": "keep-password"}])
def test_invalid_saved_config_does_not_crash_or_erase_valid_credentials(tmp_path, monkeypatch, saved):
    directory = tmp_path / "LocalAppData" / "Clipboard Bridge"
    directory.mkdir(parents=True)
    (directory / "config.json").write_text(json.dumps(saved), encoding="utf-8")
    client = load_client(tmp_path, monkeypatch)
    assert client.config["server_port"] == client.config["host_port"] == 5088
    assert client.config["auto_sync"] is False
    assert client.config["token"] == ""
    if isinstance(saved, dict):
        assert client.config["username"] == "alice"
        assert client.config["password"] == "keep-password"


def test_account_change_during_upload_does_not_relabel_its_response(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(username="alice", password="test-one")
    source = client._sync_source_key()

    def post(*args, **kwargs):
        assert kwargs["params"]["user"] == "alice"
        client.config.update(username="bob", password="test-two")
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"id": "alice-item"})

    monkeypatch.setattr(client.requests, "post", post)
    client.push_text("demo")
    state = client._load_sync_state()
    assert state["latest_items"][source] == "alice-item"
    assert client._sync_source_key() not in state["latest_items"]
    assert client._take_local_upload_marker() is None


def test_account_change_cannot_split_a_group_download(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(username="alice", password="test-one")
    source = client._sync_source_key()
    calls = []

    def get(url, **kwargs):
        calls.append(kwargs["params"]["user"])
        client.config.update(username="bob", password="test-two")
        return SimpleNamespace(raise_for_status=lambda: None, headers={}, content=b"data")

    monkeypatch.setattr(client.requests, "get", get)
    saved = client.save_remote_files({"id": "alice-group", "type": "bundle", "files": [
        {"index": 0, "filename": "a.bin"}, {"index": 1, "filename": "b.bin"}]})
    assert calls == ["alice", "alice"]
    assert client._load_sync_state()["downloads"][source]["alice-group"] == saved
    assert client._sync_source_key() not in client._load_sync_state()["downloads"]


def test_failed_received_file_write_does_not_leave_a_partial_copy(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    original = open

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

    monkeypatch.setattr(client, "open", lambda *a, **kw: FailingWriter(original(*a, **kw)), raising=False)
    with pytest.raises(OSError):
        client.save_received("report.pdf", b"full payload")
    assert list(Path(client.RECEIVED_DIR).iterdir()) == []


def test_older_connection_check_cannot_overwrite_newer_success(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    waiting = threading.Event()
    release = threading.Event()

    def get(url, **kwargs):
        if "old-server" in url:
            waiting.set()
            assert release.wait(timeout=5)
            return SimpleNamespace(status_code=401)
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {"items": []})

    monkeypatch.setattr(client.requests, "get", get)
    old = dict(client.config, server_ip="old-server")
    new = dict(client.config, server_ip="new-server")
    thread = threading.Thread(target=client.check_connection, args=(old,))
    thread.start()
    try:
        assert waiting.wait(timeout=5)
        assert client.check_connection(new)
    finally:
        release.set()
        thread.join(timeout=5)
    assert not thread.is_alive()
    assert client._connection_state == "connected"
    assert client._connection_checked_server == "http://new-server:5088"


@pytest.mark.parametrize("lang", ["en", "it"])
@pytest.mark.parametrize("active_state,draft_status,expected_key", [
    ("connected", 401, "status_auth"), ("offline", 200, "status_connected_short"),
])
def test_settings_draft_probe_does_not_change_active_connection_status(
        tmp_path, monkeypatch, tk_test_root, lang, active_state, draft_status, expected_key):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(lang=lang, username="public-active-account")
    client._set_connection_state(active_state, "http://active.example:5088")
    generation = client._connection_check_generation
    requests_seen, saved = [], []
    monkeypatch.setattr(client, "_root", tk_test_root)
    monkeypatch.setattr(client, "save_config", lambda values: saved.append(dict(values)))

    def get(url, **kwargs):
        requests_seen.append(kwargs["params"])
        return SimpleNamespace(status_code=draft_status, raise_for_status=lambda: None,
                               json=lambda: {"items": []})

    monkeypatch.setattr(client.requests, "get", get)

    def descendants(parent):
        for child in parent.winfo_children():
            yield child
            yield from descendants(child)

    window = None
    try:
        client.open_settings()
        window = next(child for child in tk_test_root.winfo_children()
                      if isinstance(child, client.tk.Toplevel))
        controls = list(descendants(window))
        account = next(child for child in controls if isinstance(child, client.ttk.Entry)
                       and child.get() == "public-active-account")
        account.delete(0, "end")
        account.insert(0, "public-draft-account")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            tk_test_root.update()
            while not client._cmd_q.empty():
                client._cmd_q.get_nowait()()
            if requests_seen and any(isinstance(child, client.tk.Label)
                                     and child.cget("text") == client.t(expected_key)
                                     for child in controls):
                break
            time.sleep(.01)
        else:
            pytest.fail("The draft result was not displayed in Settings")
        assert requests_seen[-1]["user"] == "public-draft-account"
        assert client._connection_state == active_state
        assert client._connection_checked_server == "http://active.example:5088"
        assert client._connection_check_generation == generation
        assert client.config["username"] == "public-active-account" and saved == []
    finally:
        if window is not None and window.winfo_exists():
            tk_test_root.tk.call(window.protocol("WM_DELETE_WINDOW"))


@pytest.mark.parametrize("response_status,payload,expected", [
    (200, {"items": []}, "connected"), (401, None, "auth"), (403, None, "auth"),
    (500, None, "offline"), (200, {"page": "unrelated"}, "offline"),
    (200, {"items": "not an array"}, "offline"),
])
def test_private_connection_probe_reports_without_touching_tray_state(
        tmp_path, monkeypatch, response_status, payload, expected):
    client = load_client(tmp_path, monkeypatch)
    client._set_connection_state("connected", "http://saved.example:5088")
    generation = client._connection_check_generation
    reports = []

    def raise_status():
        if response_status >= 400:
            raise requests.HTTPError("synthetic response")

    monkeypatch.setattr(client.requests, "get", lambda *a, **kw: SimpleNamespace(
        status_code=response_status, raise_for_status=raise_status, json=lambda: payload))
    result = client.check_connection(dict(client.config, username="public-draft"), on_status=reports.append)
    assert result is (expected == "connected")
    assert reports == ["checking", expected]
    assert client._connection_state == "connected"
    assert client._connection_checked_server == "http://saved.example:5088"
    assert client._connection_check_generation == generation


def test_private_probe_cannot_cancel_a_running_saved_connection_check(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    waiting, release = threading.Event(), threading.Event()
    reports = []

    def get(url, **kwargs):
        if kwargs["params"].get("user") == "public-draft":
            return SimpleNamespace(status_code=401)
        waiting.set()
        assert release.wait(5)
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {"items": []})

    monkeypatch.setattr(client.requests, "get", get)
    worker = threading.Thread(target=client.check_connection)
    worker.start()
    try:
        assert waiting.wait(5)
        generation = client._connection_check_generation
        assert not client.check_connection(dict(client.config, username="public-draft"), on_status=reports.append)
        assert client._connection_check_generation == generation
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    assert client._connection_state == "connected" and reports == ["checking", "auth"]


@pytest.mark.parametrize("change", [
    {"username": "public-other"}, {"server_ip": "other.example"},
    {"password": "public-new-password"}, {"token": "public-new-token"},
    {"mode": "server"},
])
@pytest.mark.parametrize("kind", ["text", "image", "bundle"])
@pytest.mark.parametrize("return_to_original", [False, True])
def test_received_clipboard_cannot_commit_after_its_connection_changes(
        tmp_path, monkeypatch, change, kind, return_to_original):
    client = load_client(tmp_path, monkeypatch)
    copied, notices = [], []
    sample = tmp_path / "public.txt"
    sample.write_bytes(b"public example")
    data = {"id": "public-old-item", "type": kind, "text": "Public old-account text",
            "data": base64.b64encode(client.image_to_png(client.Image.new("RGB", (2, 2)))).decode("ascii"),
            "files": [{"index": 0, "filename": sample.name}]}

    def get(*args, **kwargs):
        original = dict(client.config)
        values = dict(client.config, **change)
        client._apply_config(values)
        if return_to_original:
            client._apply_config(original)
        return data

    monkeypatch.setattr(client, "pull_latest", get)
    monkeypatch.setattr(client, "save_remote_files", lambda value: [str(sample)])
    monkeypatch.setattr(client, "set_clipboard_text", lambda value: copied.append(value))
    monkeypatch.setattr(client, "set_clipboard_image", lambda value: copied.append(value))
    monkeypatch.setattr(client, "get_clipboard_image", lambda: None)
    monkeypatch.setattr(client, "set_clipboard_files", lambda value: copied.append(value))
    monkeypatch.setattr(client, "notify", lambda value, **kw: notices.append(value))
    client.action_get_latest()
    assert copied == [], "A previous connection must not replace the current clipboard"
    assert not client._load_sync_state().get("latest_items")
    assert client._take_local_upload_marker() is None
    assert len(notices) == 1 and client.t("remote_changed") in notices[0]


def test_nonconnection_settings_preserve_ticket_and_pending_marker(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    ticket = client._connection_ticket()
    client._set_local_upload_marker("text", "public sample")
    client._apply_config(dict(client.config, appearance="light", auto_sync=True, notify_text=False))
    assert client._connection_ticket() == ticket
    assert client._take_local_upload_marker() == ("text", "public sample")
    original = dict(client.config)
    client._apply_config(client.config)
    assert client.config == original


def test_away_and_back_drops_an_old_upload_marker(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    original = dict(client.config)
    client._set_local_upload_marker("text", "public sample")
    client._apply_config(dict(original, username="public-other"))
    client._apply_config(original)
    assert client._take_local_upload_marker() is None


def test_settings_change_does_not_wait_for_group_http_and_old_group_cannot_commit(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(username="public-first", password="public-first-password")
    source = client._sync_source_key()
    waiting, release = threading.Event(), threading.Event()
    accounts, copied, errors = [], [], []

    def get(url, **kwargs):
        accounts.append(kwargs["params"]["user"])
        waiting.set()
        assert release.wait(5)
        return SimpleNamespace(raise_for_status=lambda: None, headers={}, content=b"public example")

    def receive():
        try:
            client._copy_remote_item({"id": "public-group", "type": "bundle", "files": [
                {"index": 0, "filename": "first.txt"}, {"index": 1, "filename": "second.txt"}]})
        except Exception as error:
            errors.append(error)

    monkeypatch.setattr(client.requests, "get", get)
    monkeypatch.setattr(client, "set_clipboard_files", copied.append)
    worker = threading.Thread(target=receive)
    worker.start()
    try:
        assert waiting.wait(5)
        changer = threading.Thread(target=lambda: client._apply_config(dict(client.config, username="public-second")))
        changer.start()
        changer.join(1)
        assert not changer.is_alive(), "Settings must not wait for the network lock"
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    assert accounts == ["public-first", "public-first"] and copied == []
    assert len(errors) == 1 and isinstance(errors[0], client._ConnectionChanged)
    state = client._load_sync_state()
    assert len(state["downloads"][source]["public-group"]) == 2
    assert not state.get("latest_items")
    assert client._sync_source_key() not in state["downloads"]


@pytest.mark.parametrize("stage", ["history", "download"])
def test_auto_file_receipt_rejects_changed_source_before_local_effects(tmp_path, monkeypatch, stage):
    client = load_client(tmp_path, monkeypatch)
    items, notices, copied, cached = [], [], [], []
    path = tmp_path / "public-file.txt"
    path.write_bytes(b"public example")

    def history(limit):
        if items and stage == "history":
            client._apply_config(dict(client.config, username="public-other"))
        return list(items)

    def download(item):
        if stage == "download":
            client._apply_config(dict(client.config, username="public-other"))
        return [str(path)]

    monkeypatch.setattr(client, "fetch_history", history)
    monkeypatch.setattr(client, "save_remote_files", download)
    monkeypatch.setattr(client, "record_local_files", lambda value: cached.append(value))
    monkeypatch.setattr(client, "set_clipboard_files", copied.append)
    monkeypatch.setattr(client, "notify", lambda value, **kw: notices.append(value))
    client._auto_receive_remote_files()
    items.append({"id": "public-file", "type": "file", "filename": path.name})
    with pytest.raises(client._ConnectionChanged):
        client._auto_receive_remote_files()
    assert copied == cached == notices == []
    assert client._last_remembered_item() is None


def test_late_active_connection_check_is_ignored_after_away_and_back(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    original = dict(client.config)
    def get(*args, **kwargs):
        client._apply_config(dict(original, username="public-other"))
        client._apply_config(original)
        client._set_connection_state("offline")
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {"items": []})
    monkeypatch.setattr(client.requests, "get", get)
    assert not client.check_connection()
    assert client._connection_state == "offline"


def test_sync_discards_stale_text_then_receives_the_current_connection(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(auto_sync=True, auto_receive_files=False, monitor_clipboard=False)
    original = dict(client.config)
    copied, notices, calls = [], [], []
    class Iterations:
        step = 0
        def is_set(self): return self.step >= 2
        def wait(self, timeout): self.step += 1
    iterations = Iterations()
    def poll(known):
        calls.append(known)
        if len(calls) == 1:
            client._apply_config(dict(original, username="public-other"))
            client._apply_config(original)
            return {"id": "obsolete", "type": "text", "text": "public obsolete"}
        return {"id": "current", "type": "text", "text": "public current"}
    monkeypatch.setattr(client, "stop_event", iterations)
    monkeypatch.setattr(client, "check_connection", lambda: True)
    monkeypatch.setattr(client, "_clipboard_sequence", lambda: 10)
    monkeypatch.setattr(client, "get_clipboard_files", lambda: [])
    monkeypatch.setattr(client, "get_clipboard_image", lambda: None)
    monkeypatch.setattr(client, "get_clipboard_text", lambda: "")
    monkeypatch.setattr(client, "poll_latest", poll)
    monkeypatch.setattr(client, "set_clipboard_text", copied.append)
    monkeypatch.setattr(client, "notify", lambda value, **kw: notices.append(value))
    client.sync_loop()
    assert copied == ["public current"] and notices == [client.t("text_arrived")]
    assert client._last_remembered_item() == "current"


@pytest.mark.parametrize("sequence_available", [False, True])
@pytest.mark.parametrize("change_during_read", [False, True])
def test_switching_connections_does_not_reshare_old_clipboard_but_new_copies_work(
        tmp_path, monkeypatch, sequence_available, change_during_read):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(username="public-first", auto_sync=True, auto_receive_files=False, monitor_clipboard=False)
    uploads = []
    class Iterations:
        step = 0
        def is_set(self): return self.step >= 3
        def wait(self, timeout):
            self.step += 1
            if self.step == 1 and not change_during_read:
                client._apply_config(dict(client.config, username="public-second"))
    iterations = Iterations()
    def text():
        if iterations.step == 0 and change_during_read:
            client._apply_config(dict(client.config, username="public-second"))
        return "public fresh copy" if iterations.step == 2 else "public old clipboard"
    def post(*args, **kwargs):
        uploads.append((kwargs["params"]["user"], kwargs["json"]["text"]))
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"id": str(len(uploads))})
    monkeypatch.setattr(client, "stop_event", iterations)
    monkeypatch.setattr(client, "check_connection", lambda: True)
    monkeypatch.setattr(client, "_clipboard_sequence", lambda: (6 if iterations.step == 2 else 5)
                        if sequence_available else None)
    monkeypatch.setattr(client, "get_clipboard_files", lambda: [])
    monkeypatch.setattr(client, "get_clipboard_image", lambda: None)
    monkeypatch.setattr(client, "get_clipboard_text", text)
    monkeypatch.setattr(client.requests, "post", post)
    monkeypatch.setattr(client, "poll_latest", lambda known: {})
    client.sync_loop()
    expected = [] if change_during_read else [("public-first", "public old clipboard")]
    assert uploads == expected + [("public-second", "public fresh copy")]


@pytest.mark.parametrize("kind", ["text", "image", "files"])
@pytest.mark.parametrize("fresh_at", [1, 2])
def test_identical_fresh_copy_is_shared_after_switch_before_or_after_baseline(
        tmp_path, monkeypatch, kind, fresh_at):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(username="public-first", auto_sync=True, auto_receive_files=False)
    sample = tmp_path / "public.pdf"
    sample.write_bytes(b"public file")
    image = client.Image.new("RGB", (2, 2))
    uploads = []

    class Iterations:
        step = 0
        sequence = 5
        def is_set(self): return self.step >= 4
        def wait(self, timeout):
            self.step += 1
            if self.step == 1:
                client._apply_config(dict(client.config, username="public-second"))
            if self.step == fresh_at:
                self.sequence += 1
    iterations = Iterations()
    def pushed(*args):
        uploads.append(client._request_settings()["username"])
        return str(len(uploads))
    monkeypatch.setattr(client, "stop_event", iterations)
    monkeypatch.setattr(client, "check_connection", lambda: True)
    monkeypatch.setattr(client, "_clipboard_sequence", lambda: iterations.sequence)
    monkeypatch.setattr(client, "get_clipboard_files", lambda: [str(sample)] if kind == "files" else [])
    monkeypatch.setattr(client, "get_clipboard_image", lambda: image if kind == "image" else None)
    monkeypatch.setattr(client, "get_clipboard_text", lambda: "public unchanged text")
    for name in ("push_text", "push_image", "push_files"):
        monkeypatch.setattr(client, name, pushed)
    monkeypatch.setattr(client, "poll_latest", lambda known: {})
    client.sync_loop()
    assert uploads == ["public-first", "public-second"]


@pytest.mark.parametrize("kind", ["text", "image"])
def test_first_receipt_after_connection_change_does_not_echo_as_a_fresh_copy(
        tmp_path, monkeypatch, kind):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(username="public-first", auto_sync=True, auto_receive_files=False)
    uploads, notices = [], []
    clipboard = {"text": "public old text", "image": None, "sequence": 5}

    class Iterations:
        step = 0
        def is_set(self): return self.step >= 4
        def wait(self, timeout):
            self.step += 1
            if self.step == 1:
                client._apply_config(dict(client.config, username="public-second"))
    iterations = Iterations()
    def received(value):
        clipboard[kind] = value
        clipboard["sequence"] += 1
    def pushed(*args):
        uploads.append(client._request_settings()["username"])
        return str(len(uploads))
    item = {"id": "public-remote", "type": kind, "text": "public received text",
            "data": base64.b64encode(client.image_to_png(client.Image.new("RGB", (2, 2)))).decode("ascii")}
    monkeypatch.setattr(client, "stop_event", iterations)
    monkeypatch.setattr(client, "check_connection", lambda: True)
    monkeypatch.setattr(client, "_clipboard_sequence", lambda: clipboard["sequence"])
    monkeypatch.setattr(client, "get_clipboard_files", lambda: [])
    monkeypatch.setattr(client, "get_clipboard_image", lambda: clipboard["image"])
    monkeypatch.setattr(client, "get_clipboard_text", lambda: clipboard["text"])
    monkeypatch.setattr(client, "set_clipboard_" + kind, received)
    monkeypatch.setattr(client, "notify", lambda value, **kw: notices.append(value))
    for name in ("push_text", "push_image", "push_files"):
        monkeypatch.setattr(client, name, pushed)
    monkeypatch.setattr(client, "poll_latest", lambda known: item if iterations.step == 1 else {})
    client.sync_loop()
    assert uploads == ["public-first"]
    assert notices == [client.t("text_arrived" if kind == "text" else "image_arrived")]


@pytest.mark.parametrize("after_start", ["edit", "close"])
def test_late_draft_probe_does_not_apply_to_changed_or_closed_settings(
        tmp_path, monkeypatch, tk_test_root, after_start):
    client = load_client(tmp_path, monkeypatch)
    client.config["username"] = "public-active"
    waiting, release, finished = threading.Event(), threading.Event(), threading.Event()
    client._set_connection_state("offline")
    monkeypatch.setattr(client, "_root", tk_test_root)

    def get(url, **kwargs):
        waiting.set()
        assert release.wait(5)
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {"items": []})

    original = client.check_connection

    def check(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(client.requests, "get", get)
    monkeypatch.setattr(client, "check_connection", check)

    def descendants(parent):
        for child in parent.winfo_children():
            yield child
            yield from descendants(child)

    def pump_until(predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            tk_test_root.update()
            while not client._cmd_q.empty():
                client._cmd_q.get_nowait()()
            if predicate():
                return
            time.sleep(.01)
        pytest.fail("Draft test worker/UI did not finish")

    window = None
    try:
        client.open_settings()
        window = next(child for child in tk_test_root.winfo_children()
                      if isinstance(child, client.tk.Toplevel))
        controls = list(descendants(window))
        pump_until(waiting.is_set)
        assert not finished.is_set(), "The controlled HTTP response must still be pending before editing"
        if after_start == "edit":
            account = next(child for child in controls if isinstance(child, client.ttk.Entry)
                           and child.get() == "public-active")
            account.delete(0, "end")
            account.insert(0, "public-other")
            assert account.get() == "public-other", (account.state(), client.config["mode"])
        else:
            tk_test_root.tk.call(window.protocol("WM_DELETE_WINDOW"))
        release.set()
        pump_until(finished.is_set)
        if after_start == "edit":
            # The worker can finish between draining the queue and checking its
            # event. Wait for UI delivery too, not merely the network thread.
            pump_until(lambda: any(isinstance(child, client.tk.Label)
                                   and child.cget("text") == client.t("connection_changed") for child in controls))
            assert any(isinstance(child, client.tk.Label) and child.cget("text") == client.t("connection_changed")
                       for child in controls)
            button = next(child for child in controls if isinstance(child, client.ttk.Button)
                          and child.cget("text") == client.t("check_connection"))
            assert not button.instate(["disabled"])
        assert client._connection_state == "offline" and client.config["username"] == "public-active"
    finally:
        release.set()
        assert finished.wait(5)
        if window is not None and window.winfo_exists():
            tk_test_root.tk.call(window.protocol("WM_DELETE_WINDOW"))


def test_embedded_read_and_trim_are_serialized(embedded):
    from concurrent.futures import ThreadPoolExecutor
    client, address = embedded
    client.config["max_local_history"] = 1
    base = f"http://{address[0]}:{address[1]}"

    def exercise(number):
        saved = requests.post(base + "/clipboard", files={"file": ("test.bin", bytes([number]))}, timeout=5).json()
        for path in ("/clipboard/latest", "/clipboard/latest/raw", f"/clipboard/item/{saved['id']}/raw"):
            assert requests.get(base + path, timeout=5).status_code in (200, 404)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(exercise, range(16)))


@pytest.mark.parametrize("lang", ["en", "it"])
@pytest.mark.parametrize("appearance", ["dark", "light"])
def test_history_window_search_and_pagination(tmp_path, monkeypatch, lang, appearance, tk_test_root):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(lang=lang, appearance=appearance)
    app = tk_test_root
    monkeypatch.setattr(client, "_root", app)
    requests_seen = []
    hosts_seen = []

    def fetch(limit, query, kind, offset):
        requests_seen.append((query, kind, offset))
        hosts_seen.append(client.server_url())
        size = 1 if query else limit
        return {"items": [{"id": str(offset + i), "type": kind or "text", "preview": query or f"item {offset + i}"}
                          for i in range(size)], "total": 235, "has_more": offset + size < 235}

    monkeypatch.setattr(client, "fetch_history_page", fetch)
    monkeypatch.setattr(client, "fetch_item", lambda item_id: {"id": item_id, "type": "text", "text": f"Full item {item_id}"})

    def widgets(parent):
        for child in parent.winfo_children():
            yield child
            yield from widgets(child)

    def until(predicate):
        deadline = time.monotonic() + 4
        while not predicate():
            assert time.monotonic() < deadline
            app.update()
            time.sleep(.02)

    try:
        client.open_history_window()
        window = next(child for child in app.winfo_children() if isinstance(child, client.tk.Toplevel))
        all_widgets = list(widgets(window))
        listing = next(child for child in all_widgets if isinstance(child, client.ttk.Treeview))
        until(lambda: len(listing.get_children()) == 100)
        app.update()
        style = client.ttk.Style(app)
        assert "Treeitem.indicator" not in str(style.layout("Treeview.Item"))
        image_column = listing.bbox("0", "#0")
        content_column = listing.bbox("0", "content")
        assert image_column[2] >= listing._item_icons["text"].width() + 12
        assert image_column[0] + image_column[2] <= content_column[0]
        assert not listing.item("0", "text")
        assert "Glass." in str(style.layout("TButton"))
        progress = next(child for child in all_widgets if isinstance(child, client.ttk.Progressbar))
        assert progress.winfo_height() <= 5
        assert not any(isinstance(child, client.ttk.Notebook) for child in all_widgets)
        assert sum(bool(listing.bbox(row)) for row in listing.get_children()) >= 17
        scroll = next(child for child in listing.master.winfo_children() if isinstance(child, client.ttk.Scrollbar))
        scroll.event_generate("<ButtonPress-1>", x=4, y=12)
        scroll.event_generate("<B1-Motion>", x=4, y=150)
        scroll.event_generate("<ButtonRelease-1>", x=4, y=150)
        app.update()
        assert listing.yview()[0] > 0
        listing.yview_moveto(0)
        client.open_history_window()
        assert len([child for child in app.winfo_children() if isinstance(child, client.tk.Toplevel)]) == 1
        window.geometry("760x480")
        app.update()
        assert sum(bool(listing.bbox(row)) for row in listing.get_children()) >= 10
        preview = next(child for child in all_widgets if isinstance(child, client.tk.Text))
        assert not preview.winfo_ismapped()
        preview_toggle = next(child for child in all_widgets if child.winfo_name() == "preview")
        preview_toggle.invoke()
        app.update()
        assert preview.winfo_ismapped()
        assert preview.winfo_rooty() + preview.winfo_height() <= window.winfo_rooty() + window.winfo_height()
        for child in all_widgets:
            if isinstance(child, client.ttk.Button) and child.winfo_ismapped():
                assert child.winfo_rooty() + child.winfo_height() <= window.winfo_rooty() + window.winfo_height()
                assert child.winfo_rootx() + child.winfo_width() <= window.winfo_rootx() + window.winfo_width()
        next_button = next(child for child in all_widgets if child.winfo_name() == "next")
        for name, key in (("settings", "settings"), ("delete", "delete"), ("refresh", "refresh"), ("next", "next")):
            button = next(child for child in all_widgets if child.winfo_name() == name)
            assert button.cget("text") == client.t(key).rstrip("\u2026")
            assert button.winfo_width() >= button.winfo_reqwidth()
        next_button.invoke()
        until(lambda: len(listing.get_children()) == 100 and "item 100" in listing.item("0", "values")[0])
        entry = next(child for child in all_widgets if isinstance(child, client.ttk.Entry)
                     and not isinstance(child, client.ttk.Combobox))
        variable = client.tk.StringVar(master=app, name=entry.cget("textvariable"))
        variable.set("report")
        selector = next(child for child in all_widgets if isinstance(child, client.ttk.Radiobutton)
                        and child.cget("text") == client.t("file_type"))
        selector.invoke()
        until(lambda: len(listing.get_children()) == 1 and "report" in listing.item("0", "values")[0])
        assert requests_seen[-1] == ("report", "file", 0)
        monkeypatch.setattr(client, "_local_load", lambda: pytest.fail("History must use the selected host, not the local copy log"))
        assert not any(isinstance(child, client.ttk.Radiobutton)
                       and child.cget("text") == client.t("tab_local") for child in all_widgets)
        client._apply_config(dict(client.config, mode="server", host_port=5089))
        until(lambda: hosts_seen[-1] == "http://127.0.0.1:5089" and bool(listing.get_children()))
        assert len(listing.get_children()) == 1
        assert listing.item("0", "values")[0] == "report"
        assert next_button.winfo_ismapped()
        assert next(child for child in all_widgets if child.winfo_name() == "delete").winfo_ismapped()
        for name in ("receive", "send", "add_files"):
            button = next(child for child in all_widgets if child.winfo_name() == name)
            assert button.winfo_ismapped()
            assert button.winfo_width() >= button.winfo_reqwidth()
        scrollbar = next(child for child in all_widgets if isinstance(child, client.ttk.Scrollbar))
        assert "Slim" in scrollbar.cget("style")
        assert "uparrow" not in str(client.ttk.Style(app).layout("Slim.Vertical.TScrollbar"))
        for scroll in (child for child in all_widgets if isinstance(child, client.ttk.Scrollbar) and child.winfo_ismapped()):
            assert 6 <= scroll.winfo_width() <= 14
        close_command = window.protocol("WM_DELETE_WINDOW")
        app.tk.call(close_command)
        app.update()
        assert not window.winfo_exists()
    finally:
        for child in app.winfo_children():
            child.destroy()


def test_tray_left_click_opens_history_without_upload(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    monkeypatch.setattr(client, "_run_bg", lambda *args: pytest.fail("Left-click must not upload"))
    defaults = [item for item in client.build_menu().items if item.default]
    assert len(defaults) == 1
    assert defaults[0].text == client.t("history")
    defaults[0](None)
    assert client._cmd_q.get_nowait() is client.open_history_window


@pytest.mark.parametrize("lang", ["en", "it"])
def test_modern_settings_scroll_and_invalid_ports(tmp_path, monkeypatch, lang, tk_test_root):
    client = load_client(tmp_path, monkeypatch)
    client.config["lang"] = lang
    app = tk_test_root
    monkeypatch.setattr(client, "_root", app)
    monkeypatch.setattr(client, "check_connection", lambda *args, **kwargs: True)

    def descendants(parent):
        for child in parent.winfo_children():
            yield child
            yield from descendants(child)

    try:
        client.open_settings()
        window = next(child for child in app.winfo_children() if isinstance(child, client.tk.Toplevel))
        window.geometry("700x520")
        app.update()
        widgets = list(descendants(window))
        notebook = next(child for child in widgets if isinstance(child, client._SettingsNavigation))
        client.open_settings()
        assert len([child for child in app.winfo_children() if isinstance(child, client.tk.Toplevel)]) == 1
        for tab in notebook.tabs():
            notebook.select(tab)
            app.update()
            page = window.nametowidget(tab)
            canvas = next(child for child in page.winfo_children() if isinstance(child, client.tk.Canvas))
            assert canvas.bbox("all")[3] >= canvas.winfo_height() or canvas.yview() == (0.0, 1.0)
            canvas.yview_moveto(1)
            app.update()
            assert canvas.winfo_width() > 450
        port = next(child for child in widgets if isinstance(child, client.ttk.Entry) and child.get() == "5088")
        port.delete(0, "end")
        port.insert(0, "-1")
        save = next(child for child in widgets if isinstance(child, client.ttk.Button) and child.cget("text") == client.t("save"))
        save.invoke()
        app.update()
        assert client.config["server_port"] == client.config["host_port"] == 5088
        assert any(isinstance(child, client.ttk.Label) and child.cget("text") == client.t("err_ports") for child in widgets)
        assert save.winfo_ismapped()
        assert save.winfo_rooty() + save.winfo_height() <= window.winfo_rooty() + window.winfo_height()
    finally:
        for child in app.winfo_children():
            child.destroy()


def fake_native_hotkey_api(client, monkeypatch, rejected_key=None):
    workers = []

    class Native:
        def __init__(self):
            self.messages = client.queue.Queue()
            self.registered, self.removed = [], []

        def PeekMessageW(self, *_args):
            return 0

        def RegisterHotKey(self, _window, number, modifiers, key):
            self.registered.append((number, modifiers, key))
            return key != rejected_key

        def UnregisterHotKey(self, _window, number):
            self.removed.append(number)
            return True

        def GetMessageW(self, pointer, *_args):
            code, number = self.messages.get(timeout=5)
            message = client.ctypes.cast(pointer, client.ctypes.POINTER(client.wintypes.MSG)).contents
            message.message, message.wParam = code, number
            return 0 if code == 0x12 else 1

        def PostThreadMessageW(self, _thread, code, number, _data):
            self.messages.put((code, number))
            return True

    def api():
        native = Native()
        workers.append(native)
        return native, SimpleNamespace(GetCurrentThreadId=lambda: len(workers))

    monkeypatch.setattr(client, "_native_hotkey_api", api)
    return workers


def test_history_hotkey_queues_gui_and_replaces_existing_bindings(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    workers = fake_native_hotkey_api(client, monkeypatch)
    monkeypatch.setattr(client, "_run_bg", lambda *_: pytest.fail("History must not transfer data"))
    monkeypatch.setattr(client, "notify", lambda *_: pytest.fail("Unexpected hotkey error"))
    try:
        assert client.register_hotkeys() == []
        assert workers[0].registered == [(1, 0x4003, ord("C")), (2, 0x4003, ord("V")),
                                          (3, 0x4003, ord("H"))]
        workers[0].messages.put((0x312, 3))
        assert client._cmd_q.get(timeout=1) is client.toggle_history_window
        client.config["hotkey_history"] = "ctrl+shift+y"
        assert client.register_hotkeys() == []
        assert workers[0].removed == [1, 2, 3]
        assert workers[1].registered[-1] == (3, 0x4006, ord("Y"))
        client.config["hotkeys_enabled"] = False
        client.register_hotkeys()
        assert workers[1].removed == [1, 2, 3]
        assert client._hotkey_worker is None
    finally:
        client.unregister_hotkeys()


def test_history_hotkey_toggles_only_history_and_cancels_pending_jobs(tmp_path, monkeypatch, tk_test_root):
    client = load_client(tmp_path, monkeypatch)
    monkeypatch.setattr(client, "_root", tk_test_root)
    monkeypatch.setattr(client, "fetch_history_page", lambda *_: {"items": [], "total": 0})
    monkeypatch.setattr(client, "_run_bg", lambda *_: pytest.fail("Toggling must not transfer data"))
    settings = client.tk.Toplevel(tk_test_root)
    settings._view_name = "settings"
    baseline = set(tk_test_root.tk.call("after", "info"))
    try:
        client.toggle_history_window()
        history = next(child for child in tk_test_root.winfo_children()
                       if getattr(child, "_view_name", None) == "history")
        client.open_history_window()
        assert len([child for child in tk_test_root.winfo_children()
                    if getattr(child, "_view_name", None) == "history"]) == 1
        client.toggle_history_window()
        assert not history.winfo_exists()
        assert settings.winfo_exists()
        assert set(tk_test_root.tk.call("after", "info")) == baseline
        client.toggle_history_window()
        tk_test_root.update()
        reopened = next(child for child in tk_test_root.winfo_children()
                        if getattr(child, "_view_name", None) == "history")
        assert reopened is not history
        client.toggle_history_window()
        assert not reopened.winfo_exists()
        assert settings.winfo_exists()
    finally:
        for child in tk_test_root.winfo_children():
            if getattr(child, "_view_name", None) == "history":
                child._close_history()
            else:
                child.destroy()


def test_history_hotkey_conflict_preserves_existing_send_and_receive(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    workers = fake_native_hotkey_api(client, monkeypatch)
    errors = []
    monkeypatch.setattr(client, "notify", errors.append)
    client.config["hotkey_send"] = "ctrl+alt+h"
    try:
        client.register_hotkeys()
        assert workers[0].registered == [(1, 0x4003, ord("H")), (2, 0x4003, ord("V"))]
        assert len(errors) == 1
    finally:
        client.unregister_hotkeys()


def test_native_hotkey_registration_conflict_and_release_on_windows(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    bindings = [("hotkey_history", "ctrl+alt+shift+f11", lambda: None)]
    first, conflicting, retry = [client._NativeHotkeys(bindings) for _ in range(3)]
    try:
        assert first.start() == []
        assert conflicting.start()
        assert not conflicting.active
        first.stop()
        assert not first.thread.is_alive()
        assert retry.start() == []
    finally:
        for worker in (first, conflicting, retry):
            worker.stop()


@pytest.mark.parametrize("combination", ["h", "ctrl", "ctrl+h,y", "ctrl+f12", "ctrl+control+h"])
def test_native_hotkeys_reject_unsafe_or_unsupported_combinations(tmp_path, monkeypatch, combination):
    client = load_client(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        client._hotkey_signature(combination)


def test_recorder_waits_for_key_release_and_never_transfers_clipboard(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    lifecycle = []
    monkeypatch.setattr(client, "unregister_hotkeys", lambda: lifecycle.append("pause"))
    monkeypatch.setattr(client, "register_hotkeys", lambda: lifecycle.append("restore"))
    monkeypatch.setattr(client, "_run_bg", lambda *_: pytest.fail("Recording must not transfer data"))
    class Value:
        def __init__(self, value):
            self.value = value
        def set(self, value):
            self.value = value
    root = SimpleNamespace(focus_force=lambda: None, bind=lambda *_args, **_kw: "binding",
                           unbind=lambda *_: None)
    button = SimpleNamespace(config=lambda **_kw: None)
    variable, enabled, status = Value("ctrl+alt+h"), Value(False), Value("")
    recorder = client._HotkeyRecorder(root, enabled, status)
    recorder.begin("hotkey_history", variable, button)
    assert lifecycle == ["pause"]
    assert recorder.press(SimpleNamespace(keysym="Control_L", state=4)) == "break"
    recorder.press(SimpleNamespace(keysym="Y", state=5))
    assert variable.value == "ctrl+alt+h"
    recorder.release(SimpleNamespace(keysym="y"))
    assert variable.value == "ctrl+shift+y" and enabled.value is True
    assert lifecycle == ["pause", "restore"]
    assert recorder.target is None
    assert status.value == client.t("hotkeys_pending")
    recorder.begin("hotkey_history", variable, button)
    recorder.press(SimpleNamespace(keysym="Escape", state=0))
    assert variable.value == "ctrl+shift+y"
    assert lifecycle[-1] == "restore"


def test_old_settings_get_history_hotkey_without_losing_credentials(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    Path(client.CONFIG_FILE).write_text(json.dumps({
        "username": "alice", "password": "example-password",
        "hotkey_send": "ctrl+shift+s", "hotkey_receive": "ctrl+shift+r",
    }), encoding="utf-8")
    saved = client.load_config()
    assert saved["hotkey_history"] == "ctrl+alt+h"
    assert saved["hotkey_send"] == "ctrl+shift+s"
    assert saved["hotkey_receive"] == "ctrl+shift+r"
    assert saved["username"] == "alice" and saved["password"] == "example-password"


@pytest.mark.parametrize("lang", ["en", "it"])
def test_settings_validate_and_persist_history_hotkey(tmp_path, monkeypatch, lang, tk_test_root):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(lang=lang, username="alice", password="example-password")
    monkeypatch.setattr(client, "_root", tk_test_root)
    monkeypatch.setattr(client, "check_connection", lambda *args, **kwargs: True)
    monkeypatch.setattr(client, "register_hotkeys", lambda *args: None)
    monkeypatch.setattr(client, "notify", lambda *_args: None)

    def descendants(parent):
        for child in parent.winfo_children():
            yield child
            yield from descendants(child)

    try:
        client.open_settings()
        tk_test_root.update()
        window = next(child for child in tk_test_root.winfo_children()
                      if getattr(child, "_view_name", None) == "settings")
        controls = list(descendants(window))
        history = next(child for child in controls if isinstance(child, client.ttk.Entry)
                       and child.get() == "ctrl+alt+h")
        save = next(child for child in controls if isinstance(child, client.ttk.Button)
                    and child.cget("text") == client.t("save"))
        assert any(isinstance(child, client.ttk.Label)
                   and child.cget("text") == client.t("lbl_hk_history") for child in controls)
        for invalid in ("alt+ctrl+c", "ctrl+not-a-real-key"):
            history.delete(0, "end")
            history.insert(0, invalid)
            save.invoke()
            tk_test_root.update()
            assert client.config["hotkey_history"] == "ctrl+alt+h"
            assert window.winfo_exists()
            assert any(isinstance(child, client.ttk.Label)
                       and child.cget("text") == client.t("err_hotkeys") for child in controls)
        history.delete(0, "end")
        history.insert(0, "CTRL+SHIFT+Y")
        save.invoke()
        tk_test_root.update()
        saved = json.loads(Path(client.CONFIG_FILE).read_text(encoding="utf-8"))
        assert saved["hotkey_history"] == "ctrl+shift+y"
        assert saved["username"] == "alice" and saved["password"] == "example-password"
        assert client.load_config()["hotkey_history"] == "ctrl+shift+y"
    finally:
        for child in tk_test_root.winfo_children():
            if child.winfo_exists():
                command = child.protocol("WM_DELETE_WINDOW")
                tk_test_root.tk.call(command) if command else child.destroy()


def test_unavailable_native_hotkey_does_not_save_settings(tmp_path, monkeypatch, tk_test_root):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(username="alice", password="example-password")
    before = dict(client.config)
    original_ticket = client._connection_ticket()
    saved_before = Path(client.CONFIG_FILE).read_bytes()
    workers = fake_native_hotkey_api(client, monkeypatch, rejected_key=ord("Y"))
    monkeypatch.setattr(client, "_root", tk_test_root)
    monkeypatch.setattr(client, "check_connection", lambda *args, **kwargs: True)
    monkeypatch.setattr(client, "notify", lambda *_: None)

    def descendants(parent):
        for child in parent.winfo_children():
            yield child
            yield from descendants(child)

    try:
        client.open_settings()
        tk_test_root.update()
        window = next(child for child in tk_test_root.winfo_children()
                      if getattr(child, "_view_name", None) == "settings")
        controls = list(descendants(window))
        username = next(child for child in controls if isinstance(child, client.ttk.Entry)
                        and child.get() == "alice")
        username.delete(0, "end")
        username.insert(0, "bob")
        buttons = [child for child in controls if isinstance(child, client.ttk.Button)
                   and child.cget("text") == client.t("set_hotkey")]
        assert len(buttons) == 3
        history = next(child for child in controls if isinstance(child, client.ttk.Entry)
                       and child.get() == "ctrl+alt+h")
        history.delete(0, "end")
        history.insert(0, "ctrl+shift+y")
        next(child for child in controls if isinstance(child, client.ttk.Button)
             and child.cget("text") == client.t("save")).invoke()
        tk_test_root.update()
        assert client.config == before
        assert client._connection_ticket() == original_ticket
        assert window.winfo_exists()
        assert Path(client.CONFIG_FILE).read_bytes() == saved_before
        assert workers[0].removed == [1, 2]
        assert set(client._hotkey_worker.active) == {1, 2, 3}
        assert any(isinstance(child, client.ttk.Label)
                   and client.t("hotkey_unavailable", e="").split(":")[0] in child.cget("text")
                   for child in controls)
    finally:
        client.unregister_hotkeys()
        for child in tk_test_root.winfo_children():
            if child.winfo_exists():
                command = child.protocol("WM_DELETE_WINDOW")
                tk_test_root.tk.call(command) if command else child.destroy()


def test_theme_preview_cancel_save_and_support_language(tmp_path, monkeypatch, tk_test_root):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(appearance="dark", username="alice", password="example-password")
    monkeypatch.setattr(client, "_root", tk_test_root)
    monkeypatch.setattr(client, "fetch_history_page", lambda *_args: {"items": [], "total": 0})
    monkeypatch.setattr(client, "check_connection", lambda *args, **kwargs: True)
    monkeypatch.setattr(client, "_run_bg", lambda action: action())
    monkeypatch.setattr(client, "register_hotkeys", lambda *args: None)
    monkeypatch.setattr(client, "notify", lambda *_args, **_kw: None)
    opened = []
    monkeypatch.setattr(client.webbrowser, "open", lambda url: opened.append(url))

    def descendants(parent):
        for child in parent.winfo_children():
            yield child
            yield from descendants(child)

    def settings():
        client.open_settings()
        tk_test_root.update()
        window = next(child for child in tk_test_root.winfo_children()
                      if getattr(child, "_view_name", None) == "settings")
        return window, list(descendants(window))

    try:
        client.open_history_window()
        tk_test_root.update()
        history = next(child for child in tk_test_root.winfo_children()
                       if getattr(child, "_view_name", None) == "history")
        window, controls = settings()
        light = next(child for child in controls if isinstance(child, client.ttk.Radiobutton)
                     and child.cget("text") == client.t("light_theme"))
        light.invoke()
        tk_test_root.update()
        assert history.cget("background") == client._PALETTES["light"]["panel"]
        listing = next(child for child in descendants(history) if isinstance(child, client.ttk.Treeview))
        light_icons = dict(listing._item_icons)
        assert client.config["appearance"] == "dark"
        note = next(child for child in controls if child.winfo_name() == "support_note")
        support = next(child for child in controls if child.winfo_name() == "support")
        for value, lang in (("Italiano", "it"), ("English", "en")):
            window._language_var.set(value)
            tk_test_root.update()
            assert note.cget("text") == client.STRINGS[lang]["support_note"]
            assert support.ui_label == client.STRINGS[lang]["support"]
        assert opened == []
        support.invoke()
        assert opened == ["https://ko-fi.com/mattboxx"]
        next(child for child in controls if isinstance(child, client.ttk.Button)
             and child.cget("text") == client.t("cancel")).invoke()
        tk_test_root.update()
        assert history.cget("background") == client._PALETTES["dark"]["panel"]
        assert listing._item_icons["text"] is not light_icons["text"]
        window, controls = settings()
        next(child for child in controls if isinstance(child, client.ttk.Radiobutton)
             and child.cget("text") == client.t("light_theme")).invoke()
        next(child for child in controls if isinstance(child, client.ttk.Button)
             and child.cget("text") == client.t("save")).invoke()
        tk_test_root.update()
        saved = json.loads(Path(client.CONFIG_FILE).read_text(encoding="utf-8"))
        assert saved["appearance"] == "light"
        assert saved["username"] == "alice" and saved["password"] == "example-password"
        assert history.cget("background") == client._PALETTES["light"]["panel"]
    finally:
        tk_test_root._appearance_override = None
        for child in tk_test_root.winfo_children():
            if child.winfo_exists():
                command = child.protocol("WM_DELETE_WINDOW")
                tk_test_root.tk.call(command) if command else child.destroy()


def test_dark_controls_never_inherit_white_hover_states(tmp_path, monkeypatch, tk_test_root):
    client = load_client(tmp_path, monkeypatch)
    monkeypatch.setattr(client, "_root", tk_test_root)
    window = client.tk.Toplevel(tk_test_root)
    try:
        style = client._modern_window(window, "dark")
        for name in ("TButton", "Command.TButton", "TEntry", "TCombobox", "TSpinbox",
                     "TCheckbutton", "Settings.TCheckbutton", "TRadiobutton",
                     "Navigation.TRadiobutton", "Segment.TRadiobutton", "Filter.TRadiobutton",
                     "Treeview.Heading"):
            for state in (("active",), ("pressed",), ("active", "selected"), ("active", "readonly"),
                          ("focus",), ("disabled",), ("disabled", "selected")):
                color = style.lookup(name, "background", state)
                assert color, (name, state)
                assert max(window.winfo_rgb(color)) < 35000, (name, state, color)
        for name in ("TEntry", "TCombobox", "TSpinbox"):
            for state in (("active",), ("readonly",), ("active", "readonly"), ("disabled",)):
                color = style.lookup(name, "fieldbackground", state)
                assert max(window.winfo_rgb(color)) < 35000, (name, state, color)
        assert "indicator" not in str(style.layout("Filter.TRadiobutton")).lower()
    finally:
        window.destroy()


def test_local_restore_never_copies_a_partial_file_group(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    copied = []
    monkeypatch.setattr(client, "set_clipboard_text", lambda value: copied.append(value))
    monkeypatch.setattr(client, "set_clipboard_files", lambda paths: copied.append(paths))
    client._copy_local_item({"type": "text", "text": "old note"})
    assert copied == ["old note"]
    first = tmp_path / "first.pdf"
    first.write_bytes(b"pdf")
    with pytest.raises(FileNotFoundError):
        client._copy_local_item({"type": "bundle", "paths": [str(first), str(tmp_path / "missing.pdf")]})
    assert copied == ["old note"]
    client._copy_local_item({"type": "bundle", "paths": [str(first)]})
    assert copied[-1] == [str(first)]


def test_image_preview_local_orientation_and_bounds(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    path = tmp_path / "photo.jpg"
    image = client.Image.new("RGB", (900, 600), "red")
    exif = image.getexif()
    exif[274] = 6
    image.save(path, exif=exif)
    preview = client._load_image_preview(str(path), False, {})
    assert preview.size == (120, 180)
    assert preview.mode == "RGBA"
    assert client._preview_target({"type": "file", "path": str(path)}, False) == str(path)
    assert client._preview_target({"type": "text", "text": "note"}, False) is None
    path.unlink()
    with pytest.raises(OSError):
        client._load_image_preview(str(path), False, {})


def sample_pdf():
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 400] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 400] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    content = b"BT /F1 36 Tf 40 300 Td (Clipboard Bridge) Tj 0 -60 Td /F1 20 Tf (Public sample PDF - first page) Tj ET"
    objects.append(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")
    output, offsets = bytearray(b"%PDF-1.4\n"), [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def test_pdf_preview_local_first_page_and_safe_lifetime(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    path = tmp_path / "document.pdf"
    path.write_bytes(sample_pdf())
    image = client._load_image_preview(str(path), False, {})
    path.unlink()  # The native document/file handle has been closed.
    assert image.size == (270, 180)
    assert image.info["preview_pages"] == 2
    assert len(image.getcolors(100000)) > 1
    assert client._preview_target({"type": "file", "path": str(path)}, False) == str(path)
    assert client._preview_target({"id": "pdf", "type": "file", "mime": "application/pdf"}, True)
    for mime in ("application/octet-stream", "application/pdf; charset=binary", ""):
        assert client._preview_target({"id": "pdf", "type": "file", "mime": mime,
                                       "filename": "document.PDF"}, True) == "/clipboard/item/pdf/raw"


@pytest.mark.parametrize("oversized", [False, True])
@pytest.mark.parametrize("kind", ["image", "pdf"])
def test_remote_image_preview_uses_snapshot_and_limits(tmp_path, monkeypatch, oversized, kind):
    client = load_client(tmp_path, monkeypatch)
    data = io.BytesIO()
    client.Image.new("RGB", (800, 600), "green").save(data, format="PNG")
    if kind == "pdf":
        data = io.BytesIO(sample_pdf())
    seen = []

    class Response:
        headers = {"Content-Length": str(33 * 1024 * 1024) if oversized else str(len(data.getvalue()))}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            seen.append("closed")

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield data.getvalue()

    def get(url, **options):
        seen.append((url, options))
        return Response()

    monkeypatch.setattr(client.requests, "get", get)
    settings = dict(client.config, server_ip="example.test", username="alice", password="example-password")
    client.config.update(server_ip="different.test", username="bob")
    item = {"id": "image", "type": "bundle", "files": [
        {"index": 0, "filename": "notes.txt"}, {"index": 1, "filename": "photo.png"}]}
    target = client._preview_target(item, True)
    assert target == "/clipboard/item/image/file/1/raw"
    if oversized:
        with pytest.raises(ValueError):
            client._load_image_preview(target, True, settings)
    else:
        preview = client._load_image_preview(target, True, settings)
        assert preview.size == ((270, 180) if kind == "pdf" else (240, 180))
        if kind == "pdf":
            assert preview.info["preview_pages"] == 2
    assert seen[0][0].startswith("http://example.test:")
    assert seen[0][1]["params"]["user"] == "alice"
    assert seen[-1] == "closed"


def test_image_preview_async_selection_and_automatic_windows_host(tmp_path, monkeypatch, tk_test_root):
    client = load_client(tmp_path, monkeypatch)
    monkeypatch.setattr(client, "_root", tk_test_root)
    monkeypatch.setattr(client, "fetch_history_page", lambda *_args: {"items": [
        {"id": "photo", "type": "image", "filename": "photo.png"},
        {"id": "note", "type": "text", "preview": "A note"}], "total": 2})
    monkeypatch.setattr(client, "fetch_item", lambda item_id: {"id": item_id, "type": "text", "text": "A complete note"})
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def load(target, is_server, settings):
        calls.append((target, is_server))
        started.set()
        release.wait(3)
        finished.set()
        return client.Image.new("RGBA", (120, 90), "red")

    monkeypatch.setattr(client, "_load_image_preview", load)

    def descendants(parent):
        for child in parent.winfo_children():
            yield child
            yield from descendants(child)

    def until(predicate):
        deadline = time.monotonic() + 5
        while not predicate():
            assert time.monotonic() < deadline
            tk_test_root.update()
            time.sleep(.02)

    try:
        client.open_history_window()
        window = next(child for child in tk_test_root.winfo_children() if getattr(child, "_view_name", None) == "history")
        controls = list(descendants(window))
        tree = next(child for child in controls if isinstance(child, client.ttk.Treeview))
        until(lambda: len(tree.get_children()) == 2)
        assert calls == []  # No image download while Preview is disabled.
        next(child for child in controls if child.winfo_name() == "preview").invoke()
        until(started.is_set)
        tree.selection_set("1")
        tk_test_root.update()
        release.set()
        until(finished.is_set)
        for _ in range(8):
            tk_test_root.update()
            time.sleep(.03)
        label = next(child for child in controls if child.winfo_name() == "preview_image")
        assert not label.winfo_ismapped()
        tree.selection_set("0")
        until(lambda: bool(label.cget("image")))
        assert label.image.width() == 120
        assert label.image.height() == 90
        before = len(calls)
        monkeypatch.setattr(client, "_local_load", lambda: pytest.fail("The Windows host uses its shared history"))
        client._apply_config(dict(client.config, mode="server"))
        until(lambda: len(calls) > before and bool(label.cget("image")))
        assert calls[-1] == ("/clipboard/item/photo/raw", True)
    finally:
        release.set()
        for child in tk_test_root.winfo_children():
            command = child.protocol("WM_DELETE_WINDOW")
            tk_test_root.tk.call(command) if command else child.destroy()


@pytest.mark.parametrize("lang", ["en", "it"])
@pytest.mark.parametrize("mode", ["client", "server"])
def test_text_preview_fetches_all_content_and_scrolls_without_copying(tmp_path, monkeypatch, tk_test_root, lang, mode):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(lang=lang, mode=mode, appearance="dark" if lang == "en" else "light",
                         username="public-example", password="example-only")
    monkeypatch.setattr(client, "_root", tk_test_root)
    text = ("Caff\u00e8 \U0001f600\U0001f1ee\U0001f1f9 line\twith spacing\r\n" * 2400) + "END OF THE COMPLETE CLIPBOARD"
    monkeypatch.setattr(client, "fetch_history_page", lambda *_args: {
        "items": [{"id": "long-note", "type": "text", "preview": text[:140]}], "total": 1})
    monkeypatch.setattr(client, "_copy_remote_item", lambda *_args, **_kw: pytest.fail("Preview must not copy"))
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    calls, heartbeat, errors = [], [], []
    ui_thread = threading.get_ident()
    monkeypatch.setattr(tk_test_root, "report_callback_exception", lambda *args: errors.append(args))

    def fetch(item_id):
        assert threading.get_ident() != ui_thread
        calls.append((item_id, client.server_url(), client.auth_params()))
        started.set()
        release.wait(5)
        finished.set()
        return {"id": item_id, "type": "text", "text": text}
    monkeypatch.setattr(client, "fetch_item", fetch)

    def descendants(parent):
        for child in parent.winfo_children():
            yield child
            yield from descendants(child)

    def until(predicate):
        deadline = time.monotonic() + 6
        while not predicate():
            assert time.monotonic() < deadline
            tk_test_root.update()
            time.sleep(.01)

    window = None
    try:
        client.open_history_window()
        window = next(child for child in tk_test_root.winfo_children() if getattr(child, "_view_name", None) == "history")
        controls = list(descendants(window))
        tree = next(child for child in controls if isinstance(child, client.ttk.Treeview))
        preview = next(child for child in controls if isinstance(child, client.tk.Text))
        rendered_lengths = []
        insert = preview.insert
        def observe_insert(index, value, *tags):
            result = insert(index, value, *tags)
            if value == text[:16384]:
                tk_test_root.after(0, lambda: rendered_lengths.append(len(preview.get("1.0", "end-1c"))))
            return result
        monkeypatch.setattr(preview, "insert", observe_insert)
        until(lambda: bool(tree.get_children()))
        assert not calls
        next(child for child in controls if child.winfo_name() == "preview").invoke()
        until(started.is_set)
        tk_test_root.after(0, lambda: heartbeat.append(True))
        until(lambda: bool(heartbeat))
        assert preview.get("1.0", "end-1c") == client.t("preview_loading")
        release.set()
        until(lambda: preview.get("1.0", "end-1c") == text)
        assert rendered_lengths and 0 < rendered_lengths[0] < len(text), "Rendering must yield to UI events"
        assert len(calls) == 1 and calls[0][0] == "long-note"
        assert calls[0][1] == ("http://127.0.0.1:5088" if mode == "server" else client.server_url())
        assert calls[0][2]["user"] == "public-example"
        assert str(preview.cget("state")) == "disabled"
        assert preview.yview()[1] < 1
        preview.yview_moveto(1)
        tk_test_root.update()
        assert preview.yview()[0] > 0 and preview.yview()[1] == 1
        assert not errors
    finally:
        release.set()
        if window is not None and window.winfo_exists():
            window._close_history()
        finished.wait(1)


@pytest.mark.parametrize("change", ["selection", "hide", "connection", "close", "empty", "failure"])
def test_text_preview_discards_stale_responses_and_handles_empty_or_failed_text(tmp_path, monkeypatch, tk_test_root, change):
    client = load_client(tmp_path, monkeypatch)
    monkeypatch.setattr(client, "_root", tk_test_root)
    monkeypatch.setattr(client, "fetch_history_page", lambda *_args: {"items": [
        {"id": "slow", "type": "text", "preview": "Incomplete extract"},
        {"id": "ready", "type": "text", "text": "Another complete note"}], "total": 2})
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    errors = []
    monkeypatch.setattr(tk_test_root, "report_callback_exception", lambda *args: errors.append(args))

    def fetch(_item_id):
        started.set()
        release.wait(5)
        finished.set()
        if change == "failure":
            raise OSError("synthetic unavailable item")
        return {"type": "text", "text": "" if change == "empty" else "OBSOLETE RESPONSE"}
    monkeypatch.setattr(client, "fetch_item", fetch)

    def descendants(parent):
        for child in parent.winfo_children():
            yield child
            yield from descendants(child)

    def until(predicate):
        deadline = time.monotonic() + 6
        while not predicate():
            assert time.monotonic() < deadline
            tk_test_root.update()
            time.sleep(.01)

    window = None
    try:
        client.open_history_window()
        window = next(child for child in tk_test_root.winfo_children() if getattr(child, "_view_name", None) == "history")
        controls = list(descendants(window))
        tree = next(child for child in controls if isinstance(child, client.ttk.Treeview))
        preview = next(child for child in controls if isinstance(child, client.tk.Text))
        toggle = next(child for child in controls if child.winfo_name() == "preview")
        until(lambda: len(tree.get_children()) == 2)
        toggle.invoke()
        until(started.is_set)
        if change == "selection":
            tree.selection_set("1")
            tk_test_root.update()
        elif change == "hide":
            toggle.invoke()
        elif change == "connection":
            client._apply_config(dict(client.config, username="new-example"))
            monkeypatch.setattr(client, "fetch_history_page", lambda *_args: {"items": [
                {"id": "new", "type": "text", "text": "New connection"}], "total": 1})
            until(lambda: preview.get("1.0", "end-1c") == "New connection")
        elif change == "close":
            window._close_history()
        release.set()
        until(finished.is_set)
        for _ in range(12):
            tk_test_root.update()
            time.sleep(.02)
        if change == "close":
            assert not window.winfo_exists()
        elif change == "hide":
            assert not preview.winfo_ismapped()
            assert "OBSOLETE" not in preview.get("1.0", "end-1c")
        else:
            expected = {"selection": "Another complete note", "connection": "New connection",
                        "empty": "", "failure": client.t("preview_unavailable")}[change]
            assert preview.get("1.0", "end-1c") == expected
        assert not errors
    finally:
        release.set()
        if window is not None and window.winfo_exists():
            window._close_history()
        finished.wait(1)


@pytest.mark.parametrize("lang", ["en", "it"])
def test_update_settings_are_clear_optional_and_persist(tmp_path, monkeypatch, tk_test_root, lang):
    client = load_client(tmp_path, monkeypatch)
    client.config.update(lang=lang, hotkeys_enabled=False)
    monkeypatch.setattr(client, "_root", tk_test_root)
    monkeypatch.setattr(client, "_run_bg", lambda action: None)
    monkeypatch.setattr(client, "notify", lambda *args, **kwargs: None)
    assert client.config["check_updates"] is True
    assert client.config["auto_install_updates"] is False
    client.open_updates_settings()
    tk_test_root.update()
    window = client._existing_view("settings")
    def descendants(parent):
        for child in parent.winfo_children():
            yield child
            yield from descendants(child)
    widgets = {child.winfo_name(): child for child in descendants(window)}
    try:
        assert client._settings_open.is_set()
        writes = []
        status_variable = client.tk.StringVar(master=window, name=widgets["update_status"].cget("textvariable"))
        trace = status_variable.trace_add("write", lambda *_args: writes.append(status_variable.get()))
        until = time.monotonic() + .45
        while time.monotonic() < until:
            tk_test_root.update()
            time.sleep(.01)
        assert writes == [], "An unchanged updater status must not repeatedly redraw the form"
        status_variable.trace_remove("write", trace)
        assert widgets["update_cancel"].cget("text") != client.t("cancel")
        assert str(widgets["update_install"].cget("state")) == "disabled"
        widgets["auto_install_updates"].invoke()
        widgets["check_updates"].invoke()
        assert str(widgets["auto_install_updates"].cget("state")) == "disabled"
        widgets["check_updates"].invoke()
        assert not tk_test_root.getvar(widgets["auto_install_updates"].cget("variable"))
        widgets["auto_install_updates"].invoke()
        next(child for child in widgets.values() if isinstance(child, client.ttk.Button)
             and child.cget("text") == client.t("save")).invoke()
        assert client.config["check_updates"] and client.config["auto_install_updates"]
        assert not client._settings_open.is_set()
        saved = json.loads(Path(client.CONFIG_FILE).read_text(encoding="utf-8"))
        assert saved["check_updates"] and saved["auto_install_updates"]
    finally:
        if window.winfo_exists():
            tk_test_root.tk.call(window.protocol("WM_DELETE_WINDOW"))


@pytest.mark.parametrize("value", [None, "bad", True, float("nan"), float("inf"), -1, 10**20])
def test_invalid_update_timestamps_cannot_disable_checks(tmp_path, monkeypatch, value):
    client = load_client(tmp_path, monkeypatch)
    assert client._update_timestamp({"time": value}, "time") == 0


def test_update_checks_do_not_install_without_explicit_opt_in(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    candidate = SimpleNamespace(version="99.0.0")
    monkeypatch.setattr(client.updates, "executable_architecture", lambda path: "x64")
    monkeypatch.setattr(client.updates, "check_update", lambda *args: candidate)
    notices, installs = [], []
    monkeypatch.setattr(client, "notify", lambda *args, **kwargs: notices.append(args))
    monkeypatch.setattr(client, "_download_and_apply_update", lambda *args, **kwargs: installs.append(args))
    for _ in range(2):
        client.check_for_updates()
    assert len(notices) == 1 and not installs
    client.config["auto_install_updates"] = True
    client.check_for_updates(manual=True)
    assert not installs, "A manual check must not close the app"
    client._settings_open.set()
    client.check_for_updates()
    assert not installs, "Unsaved Settings must defer automatic installation"
    client._settings_open.clear()
    client.check_for_updates()
    assert len(installs) == 1
    client._save_update_state({"last_apply_version": candidate.version, "last_apply_at": time.time()})
    client.check_for_updates()
    assert len(installs) == 1, "Failed/restarted updates must not loop automatically"


@pytest.mark.parametrize("phase", ["copy", "helper", "queued", "commit", "commit_write_failure", "cancel_write_failure", "ui_failure", "exit_failure"])
def test_update_handoff_keeps_cancellation_effective_until_ui_commit(tmp_path, monkeypatch, phase):
    client = load_client(tmp_path, monkeypatch)
    monkeypatch.setattr(client.sys, "frozen", True, raising=False)
    folder = Path(client.UPDATE_CACHE) / ("a" * 32)
    folder.mkdir(parents=True, exist_ok=True)
    payload = folder / "public-update.exe"
    payload.write_bytes(b"public sample")
    ticket = folder / "request.json"
    ticket.write_text("{}")
    candidate = SimpleNamespace(version="99.0.0", sha256=client.updates.file_digest(payload))
    client._available_payload = payload
    client._update_cancel.clear()
    monkeypatch.setattr(client, "_confirm_update_restart", lambda version: True)
    exits, disabled = [], []
    def disable(flags):
        if phase == "ui_failure":
            raise RuntimeError("synthetic widget failure")
        disabled.append(flags)
    button = SimpleNamespace(state=disable)
    monkeypatch.setattr(client, "_root", SimpleNamespace(winfo_children=lambda: [SimpleNamespace(_update_cancel_button=button)]))
    def exit_app(*args):
        if phase == "exit_failure":
            raise RuntimeError("synthetic shutdown failure")
        exits.append((ticket.parent / "commit.json").is_file())
    monkeypatch.setattr(client, "do_exit", exit_app)
    def prepare(*args, **kwargs):
        assert kwargs["cancelled"] is client._update_cancel
        if phase == "copy":
            client._update_cancel.set()
            raise client.updates.UpdateError("cancelled")
        return ticket
    def launch(path, **kwargs):
        assert path == ticket and kwargs["cancelled"] is client._update_cancel
        if phase == "helper":
            client._update_cancel.set()
            raise client.updates.UpdateError("cancelled")
    monkeypatch.setattr(client.updates, "prepare_handoff", prepare)
    monkeypatch.setattr(client.updates, "launch_handoff", launch)
    if phase in ("copy", "helper"):
        with pytest.raises(client.updates.UpdateError, match="cancelled"):
            client._download_and_apply_update(candidate)
    else:
        client._download_and_apply_update(candidate)
        if phase in ("queued", "cancel_write_failure"):
            client._update_cancel.set()
        if phase in ("commit_write_failure", "cancel_write_failure"):
            def fail(*args):
                raise OSError("synthetic write failure")
            monkeypatch.setattr(client.updates,
                "commit_handoff" if phase == "commit_write_failure" else "cancel_handoff", fail)
        client._cmd_q.get_nowait()()
    if phase == "commit":
        assert exits == [True] and disabled == [["disabled"]]
        assert client._update_status[0] == "installing"
    else:
        assert exits == [] and not (folder / "commit.json").exists()
        assert not client._update_maintenance.is_set()
        if phase == "queued":
            assert (folder / "cancel.json").is_file() and client._update_status[0] == "cancelled"


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


@pytest.fixture()
def clipboard_api(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)
    state = SimpleNamespace(failure=None, events=[], payload=None)
    handle, pointer, owner = 0x100000042, 0x100000084, 0x100000126

    def function(name, result):
        def call(*args):
            state.events.append((name, args))
            return 0 if state.failure == name else result
        return call

    user32 = SimpleNamespace(
        CreateWindowExW=function("window", owner),
        DestroyWindow=function("destroy", True),
        OpenClipboard=function("open", True),
        CloseClipboard=function("close", True),
        EmptyClipboard=function("empty", True),
        SetClipboardData=function("set", handle),
    )
    kernel32 = SimpleNamespace(
        GlobalAlloc=function("allocate", handle),
        GlobalLock=function("lock", pointer),
        GlobalUnlock=function("unlock", True),
        GlobalFree=function("free", 0),
    )

    def copy(destination, data, size):
        state.events.append(("copy", (destination, size)))
        if state.failure == "copy":
            raise OSError("synthetic memory copy failure")
        state.payload = bytes(data[:size])

    monkeypatch.setattr(client.ctypes, "windll", SimpleNamespace(user32=user32, kernel32=kernel32))
    monkeypatch.setattr(client.ctypes, "memmove", copy)
    monkeypatch.setattr(client.time, "sleep", lambda value: None)
    return client, state, handle, pointer, owner


def write_sample_clipboard(client, kind, tmp_path):
    if kind == "image":
        client.set_clipboard_image(client.Image.new("RGB", (2, 2), "red"))
    else:
        path = tmp_path / "public-example.pdf"
        path.write_bytes(b"public sample")
        client.set_clipboard_files([str(path)])


@pytest.mark.parametrize("invalid_member", ["missing", "directory", "empty", "none"])
@pytest.mark.parametrize("lang", ["en", "it"])
def test_native_file_group_rejects_every_unavailable_member_before_clipboard_access(
        clipboard_api, tmp_path, invalid_member, lang):
    client, state, *_ = clipboard_api
    client.config["lang"] = lang
    present = tmp_path / "public-note.txt"
    present.write_bytes(b"public example")
    invalid = {
        "missing": str(tmp_path / "missing.pdf"), "directory": str(tmp_path),
        "empty": "", "none": None,
    }[invalid_member]
    with pytest.raises(FileNotFoundError) as error:
        client.set_clipboard_files([str(present), invalid])
    assert str(error.value) == client.t("unavailable")
    assert state.events == [], "Do not replace the clipboard with only part of a group"
    assert present.read_bytes() == b"public example"


def test_native_file_group_keeps_generator_order_unicode_and_empty_files(clipboard_api, tmp_path):
    client, state, *_ = clipboard_api
    paths = [tmp_path / "public-\u03b1.txt", tmp_path / "public-\u00e9.shortcut"]
    for path in paths:
        path.write_bytes(b"")
    client.set_clipboard_files(path for path in reversed(paths))
    assert state.payload == client._build_hdrop([str(path) for path in reversed(paths)])
    assert [name for name, _ in state.events].count("set") == 1


@pytest.mark.parametrize("as_generator", [False, True])
def test_native_empty_file_selection_keeps_previous_clipboard(clipboard_api, as_generator):
    client, state, *_ = clipboard_api
    with pytest.raises(ValueError) as error:
        client.set_clipboard_files(iter(()) if as_generator else [])
    assert str(error.value) == client.t("unavailable")
    assert state.events == []


def test_incomplete_received_group_is_not_remembered_or_announced_as_copied(
        clipboard_api, tmp_path, monkeypatch):
    client, state, *_ = clipboard_api
    present = tmp_path / "public-note.txt"
    present.write_bytes(b"public example")
    paths = [str(present), str(tmp_path / "removed-before-copy.pdf")]
    remembered, markers, notices = [], [], []
    monkeypatch.setattr(client, "pull_latest", lambda: {"id": "public-group", "type": "bundle"})
    monkeypatch.setattr(client, "save_remote_files", lambda item: paths)
    monkeypatch.setattr(client, "_remember_item", lambda *a, **kw: remembered.append(a))
    monkeypatch.setattr(client, "_set_local_upload_marker", lambda *a: markers.append(a))
    monkeypatch.setattr(client, "notify", lambda message, **kw: notices.append(message))
    client.action_get_latest()
    assert state.events == []
    assert remembered == [] and markers == []
    assert notices == [client.t("recv_err", e=client.t("unavailable"))]
    Path(paths[1]).write_bytes(b"restored public sample")
    client.action_get_latest()
    assert state.payload == client._build_hdrop(paths)
    assert remembered == [("public-group",)]
    assert len(markers) == 1 and markers[0][0] == "files"
    assert notices[-1] == client.t("files_arrived", n=2)


@pytest.mark.parametrize("kind", ["image", "files"])
@pytest.mark.parametrize("failure", ["window", "allocate", "lock", "copy", "open", "empty", "set"])
def test_native_clipboard_failure_does_not_claim_success_or_leak_owned_memory(clipboard_api, tmp_path, kind, failure):
    client, state, handle, pointer, owner = clipboard_api
    state.failure = failure
    error = MemoryError if failure == "allocate" else OSError
    with pytest.raises(error):
        write_sample_clipboard(client, kind, tmp_path)
    names = [name for name, _ in state.events]
    if failure in ("window", "allocate", "lock", "copy", "open"):
        assert "empty" not in names, "Do not clear the previous clipboard before preparation succeeds"
    if "allocate" in names and failure != "allocate":
        assert [args for name, args in state.events if name == "free"] == [(handle,)]
    else:
        assert "free" not in names
    assert names.count("unlock") == (1 if "lock" in names and failure != "lock" else 0)
    assert names.count("close") == (1 if "open" in names and failure != "open" else 0)
    assert names.count("destroy") == (0 if failure == "window" else 1)
    assert names.count("open") <= 10


@pytest.mark.parametrize("kind,format_id", [("image", 8), ("files", 15)])
def test_native_clipboard_success_transfers_memory_to_windows_once(clipboard_api, tmp_path, kind, format_id):
    client, state, handle, pointer, owner = clipboard_api
    write_sample_clipboard(client, kind, tmp_path)
    names = [name for name, _ in state.events]
    assert names == ["window", "allocate", "lock", "copy", "unlock", "open", "empty", "set", "close", "destroy"]
    assert [args for name, args in state.events if name == "open"] == [(owner,)]
    creation = next(args for name, args in state.events if name == "window")
    assert creation[8] == -3 and creation[3] & 0x10000000 == 0  # HWND_MESSAGE, no WS_VISIBLE.
    assert [args for name, args in state.events if name == "set"] == [(format_id, handle)]
    assert [args[0] for name, args in state.events if name == "copy"] == [pointer]
    assert "free" not in names, "Transferred memory is owned by Windows"
    assert client.ctypes.windll.kernel32.GlobalAlloc.restype is client.ctypes.c_void_p
    assert client.ctypes.windll.user32.SetClipboardData.restype is client.ctypes.c_void_p
    if kind == "image":
        assert int.from_bytes(state.payload[:4], "little") == 40  # DIB header, not BMP file header.
    else:
        assert state.payload == client._build_hdrop([str(tmp_path / "public-example.pdf")])


@pytest.mark.parametrize("kind", ["image", "files"])
def test_native_clipboard_retries_temporary_contention_with_the_same_owner(clipboard_api, tmp_path, monkeypatch, kind):
    client, state, handle, pointer, owner = clipboard_api
    attempts, delays = [], []
    original = client.ctypes.windll.user32.OpenClipboard

    def open_clipboard(window):
        attempts.append(window)
        original(window)
        return len(attempts) >= 3

    monkeypatch.setattr(client.ctypes.windll.user32, "OpenClipboard", open_clipboard)
    monkeypatch.setattr(client.time, "sleep", delays.append)
    write_sample_clipboard(client, kind, tmp_path)
    assert attempts == [owner, owner, owner]
    assert delays == [0.05, 0.05]
    assert [name for name, _ in state.events].count("close") == 1
    assert not any(name == "free" for name, _ in state.events)


@pytest.mark.parametrize("failure", ["window", "allocate", "lock", "copy", "open", "empty", "set"])
def test_failed_native_image_receive_keeps_cursor_and_does_not_notify_success(clipboard_api, monkeypatch, failure):
    client, state, *_ = clipboard_api
    state.failure = failure
    image = client.Image.new("RGB", (2, 2), "red")
    data = {"id": "public-image", "type": "image",
            "data": base64.b64encode(client.image_to_png(image)).decode("ascii")}
    remembered, markers, notices = [], [], []
    monkeypatch.setattr(client, "pull_latest", lambda: data)
    monkeypatch.setattr(client, "get_clipboard_image", lambda: None)
    monkeypatch.setattr(client, "_remember_item", lambda *a, **kw: remembered.append(a))
    monkeypatch.setattr(client, "_set_local_upload_marker", lambda *a: markers.append(a))
    monkeypatch.setattr(client, "notify", lambda message, **kw: notices.append(message))
    client.action_get_latest()
    assert remembered == [] and markers == []
    assert len(notices) == 1 and notices[0] != client.t("image_recv")


def load_clipboard_worker():
    path = Path(__file__).with_name("windows_clipboard_worker.py")
    spec = importlib.util.spec_from_file_location("clipboard_worker_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("station_name", ["WinSta0", "other-station", ""])
def test_native_worker_rejects_wrong_station_before_clipboard_access(monkeypatch, station_name):
    worker = load_clipboard_worker()

    def information(handle, kind, buffer, size, needed):
        buffer.value = station_name
        return True

    user32 = SimpleNamespace(
        CreateWindowStationW=lambda *args: 123,
        SetProcessWindowStation=lambda handle: True,
        GetProcessWindowStation=lambda: 123,
        GetUserObjectInformationW=information,
    )
    monkeypatch.setattr(worker.ctypes, "WinDLL", lambda *args, **kw: user32)
    with pytest.raises(RuntimeError, match="isolation was not established"):
        worker.isolate_clipboard()


def test_native_worker_never_attaches_to_an_existing_fallback_station(monkeypatch):
    worker = load_clipboard_worker()
    attempts = []

    def create(name, flags, access, security):
        attempts.append((name, flags))
        return 0

    user32 = SimpleNamespace(
        CreateWindowStationW=create,
        SetProcessWindowStation=lambda handle: pytest.fail("No private station was created"),
        GetProcessWindowStation=lambda: pytest.fail("No private station was created"),
        GetUserObjectInformationW=lambda *args: pytest.fail("No private station was created"),
    )
    monkeypatch.setattr(worker.ctypes, "WinDLL", lambda *args, **kw: user32)
    monkeypatch.setattr(worker.ctypes, "get_last_error", lambda: 5 if len(attempts) == 1 else 183)
    with pytest.raises(OSError) as error:
        worker.isolate_clipboard()
    assert error.value.errno == 183
    assert len(attempts) == 2 and all(flags == 1 for _, flags in attempts)
    assert attempts[1][0] is None  # CREATE_ONLY, not an existing unnamed station.


def test_native_worker_does_not_run_checks_when_isolation_is_unavailable(monkeypatch, capsys):
    worker = load_clipboard_worker()
    monkeypatch.setattr(worker.sys, "argv", ["windows_clipboard_worker.py"])
    monkeypatch.setattr(worker, "isolate_clipboard",
                        lambda: (_ for _ in ()).throw(OSError(5, "synthetic permission denial")))
    monkeypatch.setattr(worker, "run_checks", lambda *args: pytest.fail("Do not touch an unisolated clipboard"))
    assert worker.main() == 77
    assert json.loads(capsys.readouterr().out) == {
        "status": "unavailable", "reason": "private_clipboard_unavailable", "error_code": 5,
    }


def test_real_clipboard_round_trip_uses_a_private_window_station():
    worker = Path(__file__).with_name("windows_clipboard_worker.py")
    result = subprocess.run([sys.executable, str(worker)], capture_output=True, text=True, timeout=30)
    if result.returncode == 77 and os.environ.get("GITHUB_ACTIONS") != "true":
        pytest.skip("Windows refused a fresh private clipboard; interactive clipboard was not used")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {
        "status": "passed", "private_station": True, "image_pixels": True,
        "unicode_file_group": True, "background_threads": True,
    }


def test_runtime_data_uses_user_writable_folders(tmp_path, monkeypatch):
    client = load_client(tmp_path, monkeypatch)

    assert client.APP_VERSION == (Path(__file__).parents[1] / "VERSION").read_text(encoding="ascii").strip()
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
    monkeypatch.setattr(client, "check_connection", lambda *args, **kwargs: True)
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
    monkeypatch.setattr(client, "check_connection", lambda *args, **kwargs: True)
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
    monkeypatch.setattr(second, "check_connection", lambda *args, **kwargs: True)
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
    monkeypatch.setattr(client, "check_connection", lambda *args, **kwargs: True)
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
    monkeypatch.setattr(client, "check_connection", lambda *args, **kwargs: True)
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
