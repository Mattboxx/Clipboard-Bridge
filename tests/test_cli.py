"""cb_cli against the real standalone server running on a loopback port."""

import importlib.util
import io
import json
import sys
import threading
import uuid
import zipfile
from pathlib import Path

import pytest
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cb_cli  # noqa: E402

SERVER_FILE = ROOT / "clipboard_bridge-Server.py"
CB_VARS = ("CB_URL", "CB_TOKEN", "CB_TOKEN_FILE", "CB_USER", "CB_PASSWORD", "CB_PASSWORD_FILE")


@pytest.fixture()
def live(tmp_path, monkeypatch):
    """Serve a fresh server (shared token + one account) and yield its base URL."""
    data = tmp_path / "server-data"
    monkeypatch.setenv("CLIPBOARD_DATA_DIR", str(data))
    monkeypatch.setenv("CLIPBOARD_TOKEN", "shared-token")
    monkeypatch.setenv("CLIPBOARD_PASSWORD", "shared-web-password")
    monkeypatch.setenv("CLIPBOARD_ACCOUNTS", "alice:p&ss?word")
    monkeypatch.setenv("CLIPBOARD_MAX_HISTORY", "5")
    monkeypatch.setenv("CLIPBOARD_MAX_UPLOAD_MB", "1")
    name = "clipboard_bridge_server_cli_test_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(name, SERVER_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    httpd = make_server("127.0.0.1", 0, module.app, threaded=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    for var in CB_VARS:
        monkeypatch.delenv(var, raising=False)
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        sys.modules.pop(name, None)


@pytest.fixture()
def shared(live, monkeypatch):
    monkeypatch.setenv("CB_URL", live)
    monkeypatch.setenv("CB_TOKEN", "shared-token")
    return live


class FakeStdin:
    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)

    def isatty(self) -> bool:
        return False


def run(capsys, *argv):
    cb_cli.main(list(argv))
    captured = capsys.readouterr()
    return captured.out, captured.err


def fail(capsys, *argv):
    with pytest.raises(SystemExit) as exc:
        cb_cli.main(list(argv))
    return exc.value.code, capsys.readouterr().err


def test_text_round_trip_with_unicode(shared, capsys):
    out, err = run(capsys, "push", "-t", "héllo ✓\nsecond line")
    assert err.startswith("sent text ")
    out, _ = run(capsys, "pull")
    assert out == "héllo ✓\nsecond line"


def test_stdin_text_and_named_binary(shared, capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "stdin", FakeStdin("from a pipe\n".encode()))
    run(capsys, "push")
    assert run(capsys, "pull")[0] == "from a pipe\n"

    blob = bytes(range(256)) * 4
    monkeypatch.setattr(sys, "stdin", FakeStdin(blob))
    _, err = run(capsys, "push", "-n", "blob.dat")
    assert err.startswith("sent file ")
    dest = tmp_path / "blob-out.dat"
    run(capsys, "pull", "-o", str(dest))
    assert dest.read_bytes() == blob


def test_file_keeps_bytes_name_and_mime(shared, capsys, tmp_path, monkeypatch):
    png = b"\x89PNG\r\n\x1a\n" + bytes(range(64))
    source = tmp_path / "pic ü.png"
    source.write_bytes(png)
    _, err = run(capsys, "push", str(source))
    assert err.startswith("sent image ")
    out_dir = tmp_path / "dl"
    out_dir.mkdir()
    run(capsys, "pull", "-o", str(out_dir))
    assert (out_dir / "pic ü.png").read_bytes() == png
    out, _ = run(capsys, "ls", "--json")
    item = json.loads(out)["items"][0]
    assert item["filename"] == "pic ü.png" and item["mime"] == "image/png"

    code, err = fail(capsys, "pull", "-o", str(out_dir))
    assert code == 1 and "exists" in err
    run(capsys, "pull", "-f", "-o", str(out_dir))


def test_several_files_form_one_bundle(shared, capsys, tmp_path):
    first, second = tmp_path / "one two.txt", tmp_path / "b.txt"
    first.write_text("one")
    second.write_text("two")
    _, err = run(capsys, "push", str(first), str(second))
    assert "bundle" in err and "(2 files)" in err
    archive = tmp_path / "bundle.zip"
    run(capsys, "pull", "-o", str(archive))
    with zipfile.ZipFile(archive) as zf:
        assert sorted(zf.namelist()) == ["b.txt", "one two.txt"]
        assert zf.read("one two.txt") == b"one"


def test_ls_header_aliases_and_rm_by_id(shared, capsys):
    out, err = run(capsys, "ls")
    assert out == "" and "(empty)" in err
    run(capsys, "send", "-t", "first")
    run(capsys, "put", "-t", "second")
    out, _ = run(capsys, "list")
    lines = out.splitlines()
    assert lines[0].split()[:4] == ["ID", "TIME", "TYPE", "SIZE"]
    assert "second" in lines[1] and "first" in lines[2]
    older = lines[2].split()[0]
    run(capsys, "rm", older)
    assert run(capsys, "receive")[0] == "second"
    assert run(capsys, "get")[0] == "second"
    out, _ = run(capsys, "ls")
    assert "first" not in out and "second" in out
    run(capsys, "rm", "--all")
    assert "(empty)" in run(capsys, "ls")[1]
    code, err = fail(capsys, "pull")
    assert code == 2 and "empty" in err


def test_pull_by_id(shared, capsys):
    run(capsys, "push", "-t", "older")
    run(capsys, "push", "-t", "newer")
    out, _ = run(capsys, "ls", "--json")
    older_id = json.loads(out)["items"][1]["id"]
    assert run(capsys, "pull", older_id)[0] == "older"
    assert run(capsys, "pull")[0] == "newer"


def test_wrong_and_missing_token_are_rejected(live, capsys, monkeypatch):
    monkeypatch.setenv("CB_URL", live)
    monkeypatch.setenv("CB_TOKEN", "wrong")
    code, err = fail(capsys, "ls")
    assert code == 1 and "HTTP 401" in err and "wrong" not in err
    monkeypatch.delenv("CB_TOKEN")
    code, err = fail(capsys, "push", "-t", "x")
    assert code == 1 and "HTTP 401" in err


def test_token_file_plain_and_env_style(live, capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("CB_URL", live)
    plain = tmp_path / "token"
    plain.write_text("shared-token\n")
    monkeypatch.setenv("CB_TOKEN_FILE", str(plain))
    run(capsys, "push", "-t", "via plain file")
    envfile = tmp_path / ".env"
    envfile.write_text("OTHER=1\nCLIPBOARD_TOKEN='shared-token'\n")
    monkeypatch.setenv("CB_TOKEN_FILE", str(envfile))
    assert run(capsys, "pull")[0] == "via plain file"
    envfile.write_text("OTHER=1\n")
    code, err = fail(capsys, "pull")
    assert code == 1 and "no secret" in err
    monkeypatch.setenv("CB_TOKEN_FILE", str(tmp_path / "missing"))
    code, err = fail(capsys, "pull")
    assert code == 1 and "cannot read" in err


def test_account_mode_is_isolated_from_shared_space(live, capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("CB_URL", live)
    monkeypatch.setenv("CB_USER", "alice")
    secret = tmp_path / "pw"
    secret.write_text("p&ss?word\n")
    monkeypatch.setenv("CB_PASSWORD_FILE", str(secret))
    run(capsys, "push", "-t", "alice only")
    assert run(capsys, "pull")[0] == "alice only"

    monkeypatch.delenv("CB_USER")
    monkeypatch.delenv("CB_PASSWORD_FILE")
    monkeypatch.setenv("CB_TOKEN", "shared-token")
    assert "(empty)" in run(capsys, "ls")[1]

    monkeypatch.setenv("CB_USER", "alice")
    monkeypatch.setenv("CB_PASSWORD", "nope")
    code, err = fail(capsys, "ls")
    assert code == 1 and "HTTP 401" in err and "nope" not in err


def test_secrets_never_appear_in_urls_or_output(shared, capsys):
    out, err = run(capsys, "push", "-t", "x")
    run(capsys, "ls")
    captured = capsys.readouterr()
    assert "shared-token" not in out + err + captured.out + captured.err


def test_configuration_errors(capsys, monkeypatch):
    for var in CB_VARS:
        monkeypatch.delenv(var, raising=False)
    code, err = fail(capsys, "ls")
    assert code == 1 and "CB_URL" in err
    code, err = fail(capsys, "--url", "ftp://host", "ls")
    assert code == 1 and "http://" in err
    code, err = fail(capsys, "--url", "http://127.0.0.1:9", "ls")
    assert code == 1 and "cannot reach" in err


def test_plain_http_warning_only_for_remote_hosts(capsys, monkeypatch):
    for var in CB_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CB_TOKEN", "secret-value")
    cb_cli.Client("http://127.0.0.1:5088")
    assert capsys.readouterr().err == ""
    cb_cli.Client("http://192.0.2.10:5088")
    err = capsys.readouterr().err
    assert "unencrypted" in err and "secret-value" not in err
    cb_cli.Client("https://clip.example.com")
    assert capsys.readouterr().err == ""


def test_nothing_to_send_and_version(capsys, monkeypatch):
    monkeypatch.setenv("CB_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(sys, "stdin", FakeStdin(b""))
    code, err = fail(capsys, "push")
    assert code == 1 and "empty" in err
    with pytest.raises(SystemExit) as exc:
        cb_cli.main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.startswith("cb-cli ")


@pytest.mark.parametrize("raw", [
    b"shared-token\n",
    b"\xef\xbb\xbfshared-token\r\n",
    "shared-token\r\n".encode("utf-16"),
    "CLIPBOARD_TOKEN=shared-token\r\n".encode("utf-16"),
    b"\xef\xbb\xbfCLIPBOARD_TOKEN='shared-token'\r\n",
])
def test_secret_files_survive_windows_encodings(raw, tmp_path):
    path = tmp_path / "secret"
    path.write_bytes(raw)
    assert cb_cli.read_secret(str(path), cb_cli.TOKEN_KEYS) == "shared-token"


def test_secret_file_that_is_not_text_is_rejected(tmp_path, capsys):
    path = tmp_path / "secret"
    path.write_bytes(b"\xff\xff\xff\x80")
    with pytest.raises(SystemExit):
        cb_cli.read_secret(str(path), cb_cli.TOKEN_KEYS)
    assert "not valid" in capsys.readouterr().err


@pytest.mark.parametrize("name,expected", [
    ("report.txt", "report.txt"),
    ("pic ü.png", "pic ü.png"),
    ('a:b*c?"d<e>f|g.txt', "a_b_c__d_e_f_g.txt"),
    ("trailing. .", "trailing"),
    ("CON", "_CON"),
    ("nul.txt", "_nul.txt"),
    ("Com1.tar.gz", "_Com1.tar.gz"),
    ("console.txt", "console.txt"),
    ("...", "file"),
])
def test_windows_safe_name(name, expected):
    assert cb_cli.windows_safe_name(name) == expected


def test_received_names_are_made_windows_safe_only_on_windows(shared, capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(cb_cli, "is_windows", lambda: False)
    assert cb_cli.safe_name("a%3Ab.txt", "x") == "a:b.txt"
    monkeypatch.setattr(cb_cli, "is_windows", lambda: True)
    assert cb_cli.safe_name("a%3Ab.txt", "x") == "a_b.txt"
    assert cb_cli.safe_name("..%5C..%5CCON", "x") == "_CON"
    assert cb_cli.safe_name("C%3Aevil.txt", "x") == "C_evil.txt"
    assert cb_cli.safe_name("..", "fallback") == "file"
    monkeypatch.setattr(cb_cli, "is_windows", lambda: False)
    assert cb_cli.safe_name("C%3Aevil.txt", "x") == "C:evil.txt"
    assert cb_cli.safe_name("dir%2Fsub%2Ffile.txt", "x") == "file.txt"
    assert cb_cli.safe_name("..", "fallback") == "fallback"
    monkeypatch.setattr(cb_cli, "is_windows", lambda: True)

    monkeypatch.setattr(sys, "stdin", FakeStdin(b"payload bytes"))
    run(capsys, "push", "-n", "a:b.dat")
    out_dir = tmp_path / "dl"
    out_dir.mkdir()
    run(capsys, "pull", "-o", str(out_dir))
    assert (out_dir / "a_b.dat").read_bytes() == b"payload bytes"


def test_output_never_fails_on_unencodable_text(shared, capsys, monkeypatch):
    run(capsys, "push", "-t", "preview ✓ 😀")
    stream = io.TextIOWrapper(io.BytesIO(), encoding="ascii", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    cb_cli.main(["ls"])
    stream.flush()
    assert b"preview" in stream.buffer.getvalue()
