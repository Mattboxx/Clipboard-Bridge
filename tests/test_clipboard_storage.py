import json
from pathlib import Path

import pytest

import clipboard_storage as storage


def test_missing_history_is_an_empty_new_store(tmp_path):
    path = tmp_path / "new" / "index.json"
    assert storage.read_history(path) == []
    assert not path.exists()


@pytest.mark.parametrize("raw", [b"", b"{unfinished", b"{}", b"null", b"[null]", b'["text"]', b"\xff"])
def test_invalid_history_is_reported_without_modifying_it(tmp_path, raw):
    path = tmp_path / "index.json"
    path.write_bytes(raw)
    with pytest.raises(storage.HistoryStoreError) as raised:
        storage.read_history(path)
    assert raised.value.reason == "invalid_index"
    assert path.read_bytes() == raw
    assert str(tmp_path) not in str(raised.value)


def test_unreadable_index_is_not_an_empty_store(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError("private path and secret contents must not enter the API response")

    monkeypatch.setattr(storage, "open", denied, raising=False)
    with pytest.raises(storage.HistoryStoreError) as raised:
        storage.read_history(tmp_path / "index.json")
    assert raised.value.reason == "read_failed"
    assert "secret" not in str(raised.value) and "private path" not in str(raised.value)


def test_atomic_history_round_trip_preserves_legacy_fields_and_unicode(tmp_path):
    path = tmp_path / "data" / "index.json"
    entries = [{"type": "text", "text": "Caff\u00e8 \U0001f680\nSecond line", "legacy": {"field": True}}]
    storage.write_history(path, entries)
    assert storage.read_history(path) == entries
    assert json.loads(path.read_text(encoding="utf-8")) == entries
    assert list(path.parent.iterdir()) == [path]
    storage.write_history(path, [])
    assert storage.read_history(path) == []


@pytest.mark.parametrize("stage", ["serialize", "flush", "replace"])
def test_failed_commit_preserves_previous_index_and_removes_temporary_file(tmp_path, monkeypatch, stage):
    path = tmp_path / "index.json"
    previous = [{"type": "text", "text": "previous"}]
    storage.write_history(path, previous)
    before = path.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("disk full: do not leak private diagnostic paths")

    if stage == "serialize":
        def partial_dump(data, stream, **kwargs):
            stream.write("[")
            fail()
        monkeypatch.setattr(storage.json, "dump", partial_dump)
    elif stage == "flush":
        monkeypatch.setattr(storage.os, "fsync", fail)
    else:
        monkeypatch.setattr(storage.os, "replace", fail)
    with pytest.raises(storage.HistoryStoreError) as raised:
        storage.write_history(path, [{"type": "text", "text": "replacement"}])
    assert raised.value.reason == "write_failed"
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_invalid_new_history_never_replaces_previous_index(tmp_path):
    path = tmp_path / "index.json"
    storage.write_history(path, [{"text": "previous"}])
    before = path.read_bytes()
    with pytest.raises(storage.HistoryStoreError):
        storage.write_history(path, {"not": "a history"})
    assert path.read_bytes() == before


def test_commit_flushes_file_before_replacement(tmp_path, monkeypatch):
    events = []
    fsync, replace = storage.os.fsync, storage.os.replace

    def sync_file(fd):
        events.append("flush")
        fsync(fd)

    def replace_file(source, target):
        events.append("replace")
        assert Path(source).parent == Path(target).parent
        replace(source, target)

    monkeypatch.setattr(storage.os, "fsync", sync_file)
    monkeypatch.setattr(storage.os, "replace", replace_file)
    storage.write_history(tmp_path / "index.json", [{"text": "complete"}])
    assert events == ["flush", "replace"]
