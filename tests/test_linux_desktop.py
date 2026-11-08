import importlib.util
import os
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from pathlib import Path

import pytest
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.environ.get("CB_DESKTOP_APP_DIR", str(ROOT)))
import clipboard_bridge_linux as desktop
import clipboard_linux_shortcuts as shortcuts
import clipboard_linux_transport as transport


def wait_for(root, predicate):
    until = time.monotonic() + 7
    while time.monotonic() < until:
        root.update()
        if predicate():
            return
        time.sleep(0.01)
    pytest.fail("Timed out waiting for desktop action")


@pytest.fixture()
def server_url(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIPBOARD_DATA_DIR", str(tmp_path / "server"))
    monkeypatch.setenv("CLIPBOARD_TOKEN", "test-token")
    monkeypatch.setenv("CLIPBOARD_ACCOUNTS", "")
    monkeypatch.setenv("CLIPBOARD_ACCOUNTS_FILE", "")
    name = "clipboard_linux_test_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(name, ROOT / "clipboard_bridge-Server.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    httpd = make_server("127.0.0.1", 0, module.app, threaded=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


@pytest.fixture(scope="module")
def tk_root():
    isolated_x11 = os.environ.get("CB_TEST_ISOLATED_X11") == "1"
    if sys.platform.startswith("linux") and not isolated_x11:
        pytest.skip("GUI tests require an isolated Xvfb display")
    root = desktop.tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture()
def app(server_url, monkeypatch, tk_root):
    isolated_x11 = os.environ.get("CB_TEST_ISOLATED_X11") == "1"
    root = desktop.tk.Toplevel(tk_root)
    if not isolated_x11:
        root.withdraw()
        clipboard = b""

        def clipboard_helper(data=None, **_):
            nonlocal clipboard
            if data is None:
                return clipboard
            clipboard = data

        monkeypatch.setattr(desktop, "clipboard_text", clipboard_helper)
    else:
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    view = desktop.Desktop(root)
    view.address.set(server_url)
    view.auth = {"X-Auth-Token": "test-token"}
    root.update()
    yield view
    if not view.closed:
        view.close()


def test_buttons_transfer_preview_filter_and_delete(app, monkeypatch, tmp_path):
    text = "Project notes \U0001f680\n\nSend text, photos or files from another device."
    desktop.clipboard_text(text.encode())
    app.connect_button.invoke()
    wait_for(app.root, lambda: app.status.get().startswith("Connected"))

    app.send_button.invoke()
    wait_for(app.root, lambda: app.status.get() == "Clipboard sent")
    text_id = app.tree.get_children()[0]

    first = tmp_path / "release notes.txt"
    second = tmp_path / "budget.csv"
    first.write_bytes(b"Demo notes")
    second.write_bytes(b"day,total\n1,42")
    monkeypatch.setattr(desktop.filedialog, "askopenfilenames", lambda **_: (first, second))
    app.files_button.invoke()
    wait_for(app.root, lambda: app.status.get() == "Files sent")
    assert len(app.tree.get_children()) == 2

    archive = tmp_path / "received.zip"
    monkeypatch.setattr(desktop.filedialog, "asksaveasfilename", lambda **_: archive)
    app.receive_button.invoke()
    wait_for(app.root, lambda: app.last_saved == archive)
    with zipfile.ZipFile(archive) as group:
        assert group.read(first.name) == first.read_bytes()
        assert group.read(second.name) == second.read_bytes()
    assert not app.open_button.instate(["disabled"])
    assert not app.folder_button.instate(["disabled"])

    app.tree.selection_set(text_id)
    app.root.update()
    app.selection_buttons[0].invoke()
    wait_for(app.root, lambda: app.status.get() == "Preview loaded")
    assert app.preview.get("1.0", "end-1c") == text

    if capture := os.environ.get("CB_DESKTOP_SCREENSHOT"):
        assert os.environ.get("CB_TEST_ISOLATED_X11") == "1"
        app.root.update()
        x, y = app.root.winfo_rootx(), app.root.winfo_rooty()
        width, height = app.root.winfo_width(), app.root.winfo_height()
        subprocess.run(["scrot", "-a", f"{x},{y},{width},{height}", "-o", capture],
                       check=True, timeout=10)

    desktop.clipboard_text(b"different")
    app.selection_buttons[1].invoke()
    wait_for(app.root, lambda: app.status.get() == "Copied to the clipboard")
    assert desktop.clipboard_text().decode() == text

    app.query.set("not present")
    app.refresh_button.invoke()
    wait_for(app.root, lambda: app.status.get() == "History refreshed")
    assert not app.tree.get_children()
    app.query.set("")
    app.kind.set("Text")
    app.refresh_button.invoke()
    wait_for(app.root, lambda: app.status.get() == "History refreshed")
    assert app.tree.get_children() == (text_id,)
    app.tree.selection_set(text_id)
    app.root.update()
    monkeypatch.setattr(desktop.messagebox, "askyesno", lambda *_, **__: True)
    app.selection_buttons[2].invoke()
    wait_for(app.root, lambda: app.status.get() == "Item deleted")
    assert not app.tree.get_children()


def test_window_stays_responsive_while_connecting(app, monkeypatch):
    original = desktop.Connection.history
    entered, release = threading.Event(), threading.Event()

    def delayed(client, *args, **kwargs):
        entered.set()
        if not release.wait(5):
            raise RuntimeError("test did not release request")
        return original(client, *args, **kwargs)

    monkeypatch.setattr(desktop.Connection, "history", delayed)
    app.connect_button.invoke()
    try:
        wait_for(app.root, entered.is_set)
        assert app.busy
        app.root.after(0, app.toggle_theme)
        wait_for(app.root, lambda: app.theme == "light")
        assert app.busy
    finally:
        release.set()
    wait_for(app.root, lambda: app.status.get().startswith("Connected"))
    app.address.set("http://127.0.0.1:1234")
    assert app.client is None
    assert app.send_button.instate(["disabled"])
    assert app.auth == {}


@pytest.mark.parametrize("suffix,mime,kind", [("png", "image/png", "image"), ("pdf", "application/pdf", "file")])
def test_image_and_pdf_preview(tmp_path, suffix, mime, kind):
    image = pytest.importorskip("PIL.Image")
    if suffix == "pdf" and not desktop.shutil.which("pdftoppm"):
        pytest.importorskip("pypdfium2")
    path = tmp_path / f"example.{suffix}"
    image.new("RGB", (120, 60), (34, 84, 107)).save(path)
    mode, data = desktop.render_preview(path.read_bytes(), kind, mime, path.name, (90, 70))
    assert mode == "image"
    assert data.startswith(b"\x89PNG")


def test_user_installer_preserves_other_files(tmp_path):
    path = ROOT / "scripts" / "linux" / "install.py"
    spec = importlib.util.spec_from_file_location("linux_installer", path)
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    base = tmp_path / "personal apps"
    launcher = installer.install(base, Path(sys.executable))
    app = base / installer.APP_ID
    keep = app / "existing-file"
    keep.write_text("keep me")
    assert installer.install(base, Path(sys.executable)) == launcher
    assert keep.read_text() == "keep me"
    assert (app / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes()
    assert "Terminal=false" in launcher.read_text()
    if os.environ.get("CB_TEST_ISOLATED_X11") == "1":
        subprocess.run(["desktop-file-validate", str(launcher)], check=True, timeout=10)


def test_wayland_clipboard_uses_native_tools(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("DISPLAY", ":0")
    calls = []
    payload = "Hello \U0001f680\n".encode()

    def run(command, **kwargs):
        calls.append((command, kwargs["input"]))
        return subprocess.CompletedProcess(command, 0, stdout=payload)

    monkeypatch.setattr(transport.subprocess, "run", run)
    assert transport.clipboard_text() == payload
    transport.clipboard_text(payload)
    assert calls == [
        (["wl-paste", "--no-newline", "--type", "text"], None),
        (["wl-copy", "--type", "text/plain;charset=utf-8"], payload),
    ]


def test_automatic_sync_is_opt_in_and_does_not_echo(app, server_url):
    connection = transport.Connection(server_url, {"X-Auth-Token": "test-token"})
    connection.send_text(b"already on server")
    desktop.clipboard_text(b"already on clipboard")
    app.connect_button.invoke()
    wait_for(app.root, lambda: app.status.get().startswith("Connected"))
    assert not app.sync_enabled.get()
    app.sync_button.invoke()
    wait_for(app.root, lambda: app.sync_state is not None)
    assert connection.item()[0] == b"already on server"
    assert desktop.clipboard_text() == b"already on clipboard"

    desktop.clipboard_text(b"new local value")
    wait_for(app.root, lambda: app.status.get() == "Clipboard sent automatically")
    assert connection.item()[0] == b"new local value"

    connection.send_text(b"new remote value")
    wait_for(app.root, lambda: app.status.get() == "Clipboard received automatically")
    assert desktop.clipboard_text() == b"new remote value"
    state, message = transport.sync_text(connection, app.sync_state, desktop.clipboard_text)
    assert not message and state == app.sync_state
    assert len(connection.history(20)["items"]) == 3


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="requires Unix datagram sockets")
def test_global_shortcuts_control_the_running_window(app, tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    path = shortcuts.runtime_path()
    listener = shortcuts.ShortcutListener(path)
    app.listener = listener
    try:
        desktop.clipboard_text(b"sent by desktop shortcut")
        app.connect_button.invoke()
        wait_for(app.root, lambda: app.status.get().startswith("Connected"))
        assert shortcuts.forward(path, "send")
        wait_for(app.root, lambda: app.status.get() == "Clipboard sent")
        desktop.clipboard_text(b"something else")
        assert shortcuts.forward(path, "receive")
        wait_for(app.root, lambda: app.status.get() == "Copied to the clipboard")
        assert desktop.clipboard_text() == b"sent by desktop shortcut"
        assert shortcuts.forward(path, "toggle")
        wait_for(app.root, lambda: app.root.state() == "withdrawn")
        assert shortcuts.forward(path, "toggle")
        wait_for(app.root, lambda: app.root.state() == "normal")
    finally:
        app.listener = None
        listener.close()
