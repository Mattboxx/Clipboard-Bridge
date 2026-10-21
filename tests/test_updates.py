import hashlib
import io
import json
import os
from dataclasses import asdict, replace
from pathlib import Path
import threading

import pytest

import clipboard_updates as updates


def release(version="2.0.19", architecture="x64"):
    def asset(name):
        return {"name": name, "state": "uploaded", "size": 5, "digest": "sha256:" + hashlib.sha256(b"hello").hexdigest(),
                "browser_download_url": f"https://github.com/{updates.REPOSITORY}/releases/download/{version}/{name}"}
    return {"tag_name": version, "draft": False, "prerelease": False, "assets": [
        asset(f"Clipboard.Bridge.Portable.Windows.{architecture}.V{version}.exe"),
        asset(f"Clipboard.Bridge_windows_client_and_server_setup_{architecture}_V{version}.exe")]}


@pytest.mark.parametrize("architecture", ["x64", "arm64"])
@pytest.mark.parametrize("kind", ["installer", "portable"])
def test_select_correct_architecture_and_distribution(architecture, kind):
    candidate = updates.select_update(release(architecture=architecture), "2.0.18", architecture, kind)
    assert candidate.architecture == architecture and candidate.kind == kind
    assert candidate.version == "2.0.19" and candidate.size == 5


@pytest.mark.parametrize("version", ["2.0.18", "2.0.17", "1.9.999", "v1.0.9", "android-v1.0.0-beta.12"])
def test_no_downgrade_or_cross_component_update(version):
    assert updates.select_update(release(version), "2.0.18", "x64", "portable") is None


def test_version_comparison_is_numeric():
    assert updates.select_update(release("2.0.100"), "2.0.99", "x64", "installer")


@pytest.mark.parametrize("field,value", [("digest", None), ("digest", "sha256:wrong"),
    ("size", True), ("size", 0), ("size", updates.MAX_DOWNLOAD + 1),
    ("state", "uploading"), ("browser_download_url", "https://attacker.example/app.exe"),
    ("browser_download_url", "http://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.19/app.exe")])
def test_reject_incomplete_or_untrusted_asset_metadata(field, value):
    data = release()
    data["assets"][0][field] = value
    with pytest.raises(updates.UpdateError):
        updates.select_update(data, "2.0.18", "x64", "portable")


@pytest.mark.parametrize("draft,prerelease", [(True, False), (False, True), (None, False)])
def test_no_draft_or_beta_update(draft, prerelease):
    data = dict(release(), draft=draft, prerelease=prerelease)
    with pytest.raises(updates.UpdateError):
        updates.select_update(data, "2.0.18", "x64", "portable")


def test_duplicate_assets_are_rejected():
    data = release()
    data["assets"].append(data["assets"][0])
    with pytest.raises(updates.UpdateError):
        updates.select_update(data, "2.0.18", "x64", "portable")


@pytest.mark.parametrize("url", ["http://github.com/a", "https://github.com.attacker.example/a",
    "https://github.com@attacker.example/a", "https://github.com:444/a", "file:///C:/private", "https://github.com/a#fragment"])
def test_redirect_allowlist_rejects_untrusted_destinations(url):
    with pytest.raises(updates.UpdateError):
        updates._https(url, updates.DOWNLOAD_HOSTS)


def test_metadata_request_has_no_client_credentials():
    calls = []
    def open_url(url, **kwargs):
        calls.append((url, kwargs))
        return io.BytesIO(json.dumps(release()).encode())
    assert updates.check_update("2.0.18", "x64", "portable", open_url=open_url)
    assert calls == [(updates.RELEASE_API, {"metadata": True})]


@pytest.mark.parametrize("body", [b"not-json", b"[]", b" " * (updates.API_LIMIT + 1)],
                         ids=["not-json", "array", "oversized"])
def test_bad_or_unbounded_metadata_fails_safely(body):
    with pytest.raises(updates.UpdateError):
        updates.check_update("2.0.18", "x64", "portable", open_url=lambda *a, **kw: io.BytesIO(body))


def test_verified_download_and_progress(tmp_path, monkeypatch):
    candidate = updates.select_update(release(), "2.0.18", "x64", "portable")
    calls, marked = [], []
    monkeypatch.setattr(updates, "mark_download", lambda path, url: marked.append((path, url)))
    result = updates.download_update(candidate, tmp_path, progress=lambda *value: calls.append(value),
                                     open_url=lambda url: io.BytesIO(b"hello"))
    assert result.read_bytes() == b"hello" and result.name == candidate.name
    assert calls == [(5, 5)] and marked[0][1] == candidate.url


@pytest.mark.parametrize("body", [b"bad!!", b"hell", b"hello-too-large"])
def test_bad_download_never_leaves_executable_or_damages_existing_cache(tmp_path, body):
    untouched = tmp_path / "user-file.txt"
    untouched.write_text("keep")
    candidate = updates.select_update(release(), "2.0.18", "x64", "portable")
    with pytest.raises(updates.UpdateError, match="integrity_failed"):
        updates.download_update(candidate, tmp_path, open_url=lambda url: io.BytesIO(body))
    assert list(tmp_path.iterdir()) == [untouched]


def test_cancel_download_cleans_only_owned_partial(tmp_path):
    event = threading.Event()
    event.set()
    candidate = updates.select_update(release(), "2.0.18", "x64", "portable")
    with pytest.raises(updates.UpdateError, match="cancelled"):
        updates.download_update(candidate, tmp_path, cancelled=event, open_url=lambda url: io.BytesIO(b"hello"))
    assert not list(tmp_path.iterdir())


def helper_fixture(tmp_path, monkeypatch, kind="portable"):
    cache = tmp_path / "updates"
    folder = cache / ("a" * 32)
    folder.mkdir(parents=True)
    target = tmp_path / "Installed app & Unicode \u96ea.exe"
    target.write_bytes(b"old")
    candidate = updates.select_update(release(), "2.0.18", "x64", kind)
    payload = folder / candidate.name
    payload.write_bytes(b"hello")
    (folder / "runner.exe").write_bytes(b"old")
    request = {"schema": 1, "update": asdict(candidate), "target": str(target),
               "original_sha256": updates.file_digest(target), "parent_pid": 1234, "language": "it"}
    ticket = folder / "request.json"
    ticket.write_text(json.dumps(request))
    monkeypatch.setattr(updates, "verify_executable", lambda path, checksum, version, architecture=None:
                        None if updates.file_digest(path) == checksum else (_ for _ in ()).throw(updates.UpdateError("integrity_failed")))
    monkeypatch.setattr(updates, "_process_handle", lambda *args: 42)
    monkeypatch.setattr(updates, "_wait", lambda *args: 0)
    monkeypatch.setattr(updates, "_close_handle", lambda *args: None)
    monkeypatch.setattr(updates, "mark_download", lambda *args: None)
    return cache, ticket, target, candidate


def test_portable_update_preserves_data_and_restarts_same_path(tmp_path, monkeypatch):
    cache, ticket, target, candidate = helper_fixture(tmp_path, monkeypatch)
    config = tmp_path / "config.json"
    config.write_text('{"username":"public-example"}')
    original = config.read_bytes()
    starts = []
    monkeypatch.setattr(updates, "_shell_open", lambda path, *args, **kw: starts.append(path) or 321)
    assert updates.apply_ticket(ticket, cache) == 0
    assert target.read_bytes() == b"hello" and starts == [target]
    assert config.read_bytes() == original
    result = json.loads((ticket.parent / "result.json").read_text())
    assert result == {"state": "installed", "version": candidate.version, "pid": 321}
    assert not list(target.parent.glob(".clipboard-*.exe"))


def test_portable_restart_failure_rolls_back_and_keeps_old_app_usable(tmp_path, monkeypatch):
    cache, ticket, target, _ = helper_fixture(tmp_path, monkeypatch)
    starts = []
    def start(path, *args, **kw):
        starts.append(target.read_bytes())
        if len(starts) == 1:
            raise updates.UpdateError("launch_denied")
        return 123
    monkeypatch.setattr(updates, "_shell_open", start)
    assert updates.apply_ticket(ticket, cache) == 1
    assert target.read_bytes() == b"old" and starts == [b"hello", b"old"]
    assert json.loads((ticket.parent / "result.json").read_text())["code"] == "launch_denied"


def test_cancelled_handoff_never_replaces_or_restarts_a_manually_closed_app(tmp_path, monkeypatch):
    cache, ticket, target, _ = helper_fixture(tmp_path, monkeypatch)
    (ticket.parent / "cancel.json").write_text("{}")
    monkeypatch.setattr(updates, "_shell_open", lambda *a, **kw: pytest.fail("Cancelled helper restarted app"))
    assert updates.apply_ticket(ticket, cache) == 1
    assert target.read_bytes() == b"old"


def test_parent_must_exit_before_any_replacement(tmp_path, monkeypatch):
    cache, ticket, target, _ = helper_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(updates, "_wait", lambda *args: 258)
    monkeypatch.setattr(updates, "_shell_open", lambda *a, **kw: pytest.fail("Running parent must be left alone"))
    assert updates.apply_ticket(ticket, cache) == 1 and target.read_bytes() == b"old"


def test_install_uses_quoted_arguments_no_shell_and_checks_payload(tmp_path, monkeypatch):
    cache, ticket, target, _ = helper_fixture(tmp_path, monkeypatch, "installer")
    calls = []
    def start(path, arguments=(), **kwargs):
        calls.append((path, arguments, kwargs))
        if kwargs.get("wait"):
            target.write_bytes(b"hello")
        return 321
    monkeypatch.setattr(updates, "_shell_open", start)
    assert updates.apply_ticket(ticket, cache) == 0
    assert calls[0][2] == {"wait": True}
    assert "/DIR=" + str(target.parent) in calls[0][1] and "/LANG=italian" in calls[0][1]
    assert "/NOCLOSEAPPLICATIONS" in calls[0][1] and calls[1][0] == target


@pytest.mark.parametrize("payload", [b"invalid", b"hello"])
def test_failed_installer_restores_previous_executable(tmp_path, monkeypatch, payload):
    cache, ticket, target, _ = helper_fixture(tmp_path, monkeypatch, "installer")
    def start(path, arguments=(), **kwargs):
        if kwargs.get("wait"):
            target.write_bytes(payload)
            raise updates.UpdateError("install_failed")
        return 321
    monkeypatch.setattr(updates, "_shell_open", start)
    assert updates.apply_ticket(ticket, cache) == 1 and target.read_bytes() == b"old"


def test_helper_rejects_paths_outside_its_private_cache(tmp_path):
    ticket = tmp_path / "request.json"
    ticket.write_text("{}")
    assert updates.apply_ticket(ticket, tmp_path / "updates") == 1


def test_target_changed_before_handoff_is_not_overwritten(tmp_path, monkeypatch):
    cache, ticket, target, _ = helper_fixture(tmp_path, monkeypatch)
    target.write_bytes(b"changed by user")
    assert updates.apply_ticket(ticket, cache) == 1
    assert target.read_bytes() == b"changed by user"


def test_target_changed_while_waiting_is_neither_replaced_nor_restarted(tmp_path, monkeypatch):
    cache, ticket, target, _ = helper_fixture(tmp_path, monkeypatch)
    def changed(*args):
        target.write_bytes(b"external update")
        return 0
    monkeypatch.setattr(updates, "_wait", changed)
    monkeypatch.setattr(updates, "_shell_open", lambda *args, **kw: pytest.fail("Do not restart an unknown executable"))
    assert updates.apply_ticket(ticket, cache) == 1
    assert target.read_bytes() == b"external update"


@pytest.mark.parametrize("field,value", [("name", "../../other.exe"), ("url", "https://example.com/app.exe"),
    ("architecture", "x86"), ("executable_sha256", "bad"), ("size", True), ("version", "1.0.0-beta")])
def test_helper_revalidates_ticket_metadata(tmp_path, monkeypatch, field, value):
    cache, ticket, target, _ = helper_fixture(tmp_path, monkeypatch)
    request = json.loads(ticket.read_text())
    request["update"][field] = value
    ticket.write_text(json.dumps(request))
    assert updates.apply_ticket(ticket, cache) == 1
    assert target.read_bytes() == b"old"


def test_installer_removing_target_still_restores_old_executable(tmp_path, monkeypatch):
    cache, ticket, target, _ = helper_fixture(tmp_path, monkeypatch, "installer")
    def start(path, *args, **kwargs):
        if kwargs.get("wait"):
            target.unlink()
            raise updates.UpdateError("install_failed")
        assert target.read_bytes() == b"old"
        return 12
    monkeypatch.setattr(updates, "_shell_open", start)
    assert updates.apply_ticket(ticket, cache) == 1
    assert target.read_bytes() == b"old"


def test_cache_cleanup_only_removes_old_finished_owned_folders(tmp_path):
    now = 2_000_000_000
    old = tmp_path / ("a" * 32)
    old.mkdir()
    (old / "result.json").write_text("{}")
    (old / "runner.exe").write_bytes(b"old")
    os.utime(old / "result.json", (now - 8 * 86400,) * 2)
    active = tmp_path / ("b" * 32)
    active.mkdir()
    (active / "runner.exe").write_bytes(b"active")
    unknown = tmp_path / ("c" * 32)
    unknown.mkdir()
    (unknown / "result.json").write_text("{}")
    (unknown / "user-file.txt").write_text("preserve")
    os.utime(unknown / "result.json", (now - 8 * 86400,) * 2)
    updates.prune_finished_updates(tmp_path, now=now)
    assert not old.exists()
    assert (active / "runner.exe").read_bytes() == b"active"
    assert (unknown / "user-file.txt").read_text() == "preserve"
