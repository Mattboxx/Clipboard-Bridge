"""Optional Windows-to-Docker integration: set CLIPBOARD_TEST_SERVER_URL."""

import os
from pathlib import Path

import pytest
import requests

from test_windows_client import load_client


@pytest.mark.skipif(not os.environ.get("CLIPBOARD_TEST_SERVER_URL"), reason="No isolated live server configured")
def test_windows_client_round_trips_against_live_docker_server(tmp_path, monkeypatch):
    from urllib.parse import urlparse
    base = os.environ["CLIPBOARD_TEST_SERVER_URL"].rstrip("/")
    address = urlparse(base)
    client = load_client(tmp_path, monkeypatch)
    client.config.update(mode="client", server_ip=address.hostname, server_port=address.port,
                         username="alice", password="test-password", token="")
    auth = client.auth_params()
    assert client.check_connection()
    assert requests.get(base + "/health", timeout=5).json()["version"] == "1.0.5"
    text = "\u96ea\U0001f600\r\n\t \r\nend\r"
    text_id = client.push_text(text)
    assert client.fetch_item(text_id)["text"] == text
    assert requests.get(base + "/clipboard/latest/raw", params=auth, timeout=5).content == text.encode("utf-8")
    first = tmp_path / "one" / "same.shortcut"
    second = tmp_path / "two" / "same.shortcut"
    empty = tmp_path / "empty.bin"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"AEA1\x00" + b"x" * (2 * 1024 * 1024))
    second.write_bytes(b"another")
    empty.write_bytes(b"")
    group_id = client.push_files([first, second, empty])
    meta = client.poll_latest(group_id)
    assert "data" not in meta
    assert meta["file_count"] == 3
    restored = client.save_remote_files(meta)
    assert [Path(path).read_bytes() for path in restored] == [first.read_bytes(), second.read_bytes(), b""]
    assert len(set(restored)) == 3
    assert client.save_remote_files(meta) == restored
    next_id = client.push_text("newest text")
    assert client.poll_latest(group_id)["id"] == next_id
    assert client.poll_latest(next_id).get("text") is None
    assert requests.get(base + "/clipboard/latest/raw", timeout=5).content == b""  # shared space is isolated
    for item_id in (text_id, group_id, next_id):
        requests.delete(base + f"/clipboard/item/{item_id}", params=auth, timeout=5).raise_for_status()
