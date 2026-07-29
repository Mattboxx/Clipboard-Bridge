"""
Clipboard Bridge - Windows client.

A small tray application that exchanges clipboard content with the server:
text, images and files of any type. Received files are saved in the user's
Downloads folder. The interface is available in English (default) and Italian.

Dependencies: requests, pyperclip, pystray, pillow, keyboard.
Writing images to the clipboard uses ctypes (no pywin32 required).
"""

import io
import os
import sys
import json
import uuid
import base64
import hashlib
import queue
import socket
import mimetypes
import threading
import http.server
import ctypes
import shutil
import subprocess
import time
from ctypes import wintypes

import requests
import pyperclip
from PIL import Image, ImageGrab, ImageDraw
from pystray import Icon, MenuItem, Menu
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    import keyboard
except Exception:
    keyboard = None

# The executable may be installed under Program Files, which is read-only for
# normal users. Keep resources beside the executable and runtime data in
# user-writable folders.
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    RES_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    RES_DIR = APP_DIR

DATA_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
    "Clipboard Bridge",
)
DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
LOCAL_DIR = os.path.join(DATA_DIR, "local_history")
LOCAL_INDEX = os.path.join(LOCAL_DIR, "local_history.json")
RECEIVED_DIR = os.path.join(DOWNLOADS_DIR, "Clipboard Bridge")
HOST_DIR = os.path.join(DATA_DIR, "server_data")          # store used when this PC IS the server
HOST_ITEMS = os.path.join(HOST_DIR, "items")
HOST_INDEX = os.path.join(HOST_DIR, "index.json")
SYNC_STATE_FILE = os.path.join(DATA_DIR, "sync_state.json")
ERROR_LOG = os.path.join(DATA_DIR, "error.log")
ICON_PATH = os.path.join(RES_DIR, "icon.ico")


def _copy_legacy_dir(source, destination):
    if not os.path.isdir(source):
        return
    try:
        shutil.copytree(source, destination, dirs_exist_ok=True)
    except OSError:
        pass


def _legacy_roots():
    """Return old installation folders that may still contain user data."""
    candidates = [APP_DIR]
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        base = os.environ.get(variable)
        if base:
            candidates.append(os.path.join(base, "Clipboard Bridge"))

    roots = []
    seen = set()
    for candidate in candidates:
        normalized = os.path.normcase(os.path.abspath(candidate))
        if normalized not in seen and normalized != os.path.normcase(os.path.abspath(DATA_DIR)):
            seen.add(normalized)
            roots.append(candidate)
    return roots


def _newest_existing(paths):
    existing = [path for path in paths if os.path.isfile(path)]
    if not existing:
        return None
    return max(existing, key=lambda path: os.path.getmtime(path))


def _prepare_data_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOCAL_DIR, exist_ok=True)

    # Versions up to 2.0.0 stored data beside the executable, usually under
    # Program Files. The 2.0.1 installer moved the executable to LocalAppData,
    # so all known legacy locations must be checked.
    roots = _legacy_roots()
    old_config = _newest_existing(
        [os.path.join(root, "config.json") for root in roots]
        + [os.path.join(DATA_DIR, "config.legacy.json")]
    )
    if not os.path.exists(CONFIG_FILE) and old_config:
        try:
            shutil.copy2(old_config, CONFIG_FILE)
        except OSError:
            pass
    for root in roots:
        if not os.path.exists(LOCAL_INDEX):
            _copy_legacy_dir(os.path.join(root, "local_history"), LOCAL_DIR)
        if not os.path.exists(HOST_INDEX):
            _copy_legacy_dir(os.path.join(root, "server_data"), HOST_DIR)
        _copy_legacy_dir(os.path.join(root, "ricevuti"), RECEIVED_DIR)


_prepare_data_dirs()

DEFAULT_CONFIG = {
    "lang": "en",
    "mode": "client",          # "client" = connect to an external server; "server" = be the server
    "server_ip": "127.0.0.1",  # external server address (client mode)
    "server_port": 5088,
    "host_port": 5088,         # port this PC listens on in server mode
    "token": "",
    "username": "",            # server account name (empty = shared space)
    "password": "",            # server account password
    "auto_sync": False,
    "auto_receive_files": True,
    "monitor_clipboard": True,
    "poll_interval": 3,
    "max_local_history": 100,
    "hotkeys_enabled": True,
    "hotkey_send": "ctrl+alt+c",
    "hotkey_receive": "ctrl+alt+v",
}

stop_event = threading.Event()
_icon = None   # tray icon (pystray runs on its own thread)
_root = None   # the single hidden Tk root that owns the GUI event loop (main thread)
_cmd_q = queue.Queue()  # GUI commands from the tray thread, run on the Tk thread
_notification_action = None
_notification_lock = threading.Lock()
_sync_state_lock = threading.Lock()
_connection_lock = threading.Lock()
_connection_state = "checking"

# ---------------------------------------------------------------- translations
STRINGS = {
    "en": {
        "send": "Send clipboard  →  server",
        "recv": "Receive latest  ←  server",
        "send_file": "Send a file…",
        "open_recv": "Open received folder",
        "history": "History…",
        "autosync": "Auto-sync",
        "monitor": "Local history",
        "hotkeys": "Keyboard shortcuts",
        "language": "Language",
        "mode": "Mode",
        "mode_client": "Client (use external server)",
        "mode_server": "Server (this PC)",
        "server_on": "Server mode ON — connect to {addr}",
        "client_on": "Client mode ON",
        "status_connected": "Connection: CONNECTED ({server})",
        "status_offline": "Connection: NOT CONNECTED",
        "status_auth": "Connection: SERVER FOUND, LOGIN REJECTED",
        "status_checking": "Connection: checking...",
        "check_connection": "Check connection now",
        "connected_notice": "Connected to {server}",
        "server_addr": "Server: {addr}  (click to copy)",
        "addr_copied": "Address copied: {addr}",
        "server_err": "Cannot start server: {e}",
        "lbl_host_port": "Server port (server mode)",
        "settings": "Settings…",
        "exit": "Exit",
        "image_sent": "Image sent",
        "file_sent": "File sent",
        "files_sent": "{n} files sent",
        "text_sent": "Text sent",
        "clip_empty": "Clipboard is empty",
        "send_err": "Send error: {e}",
        "text_recv": "Text copied to the clipboard",
        "image_recv": "Image copied to the clipboard",
        "file_saved": "File saved: {name}",
        "file_arrived": "New file received: {name}\nClick to show it in the folder.",
        "no_items": "Nothing on the server",
        "recv_err": "Receive error: {e}",
        "copied": "Copied to the clipboard",
        "sent_server": "Sent to the server",
        "settings_saved": "Settings saved",
        "hotkey_err": "Hotkeys not registered: {e}",
        "no_keyboard": "The 'keyboard' library is not installed",
        "choose_files": "Choose the files to send",
        "win_history": "Clipboard Bridge - History",
        "tab_server": "Server",
        "tab_local": "Local",
        "refresh": "Refresh",
        "loading": "Loading…",
        "use": "Use",
        "delete": "Delete",
        "send_to_server": "Send to server",
        "err_title": "Error",
        "info_title": "Info",
        "unavailable": "Item no longer available.",
        "win_settings": "Clipboard Bridge - Settings",
        "lbl_ip": "Server IP",
        "lbl_port": "Port",
        "lbl_token": "Token (empty = none)",
        "lbl_user": "Account (empty = shared)",
        "lbl_pass": "Account password",
        "lbl_interval": "Clipboard check interval (s)",
        "lbl_hk_send": "Send hotkey",
        "lbl_hk_recv": "Receive hotkey",
        "hint_hk": "(e.g. ctrl+alt+c  ·  ctrl+shift+v)",
        "chk_autosync": "Automatic synchronization",
        "chk_auto_files": "Automatically download new files",
        "chk_monitor": "Record local history",
        "chk_hotkeys": "Keyboard shortcuts enabled",
        "err_numbers": "Port and interval must be whole numbers.",
        "save": "Save",
        "cancel": "Cancel",
    },
    "it": {
        "send": "Invia appunti  →  server",
        "recv": "Ricevi ultimo  ←  server",
        "send_file": "Invia un file…",
        "open_recv": "Apri cartella ricevuti",
        "history": "Cronologia…",
        "autosync": "Sincronizzazione automatica",
        "monitor": "Cronologia locale",
        "hotkeys": "Scorciatoie da tastiera",
        "language": "Lingua",
        "mode": "Modalità",
        "mode_client": "Client (usa server esterno)",
        "mode_server": "Server (questo PC)",
        "server_on": "Modalità server attiva — connettiti a {addr}",
        "client_on": "Modalità client attiva",
        "status_connected": "Connessione: COLLEGATO ({server})",
        "status_offline": "Connessione: NON COLLEGATO",
        "status_auth": "Connessione: SERVER TROVATO, ACCESSO RIFIUTATO",
        "status_checking": "Connessione: verifica in corso...",
        "check_connection": "Verifica connessione ora",
        "connected_notice": "Collegato a {server}",
        "server_addr": "Server: {addr}  (clic per copiare)",
        "addr_copied": "Indirizzo copiato: {addr}",
        "server_err": "Impossibile avviare il server: {e}",
        "lbl_host_port": "Porta server (modalità server)",
        "settings": "Impostazioni…",
        "exit": "Esci",
        "image_sent": "Immagine inviata",
        "file_sent": "File inviato",
        "files_sent": "{n} file inviati",
        "text_sent": "Testo inviato",
        "clip_empty": "Appunti vuoti",
        "send_err": "Errore invio: {e}",
        "text_recv": "Testo ricevuto negli appunti",
        "image_recv": "Immagine ricevuta negli appunti",
        "file_saved": "File salvato: {name}",
        "file_arrived": "Nuovo file ricevuto: {name}\nClicca per mostrarlo nella cartella.",
        "no_items": "Nessun elemento sul server",
        "recv_err": "Errore ricezione: {e}",
        "copied": "Copiato negli appunti",
        "sent_server": "Inviato al server",
        "settings_saved": "Impostazioni salvate",
        "hotkey_err": "Hotkey non registrate: {e}",
        "no_keyboard": "Libreria 'keyboard' non installata",
        "choose_files": "Scegli i file da inviare",
        "win_history": "Clipboard Bridge - Cronologia",
        "tab_server": "Server",
        "tab_local": "Locale",
        "refresh": "Aggiorna",
        "loading": "Caricamento…",
        "use": "Usa",
        "delete": "Elimina",
        "send_to_server": "Invia al server",
        "err_title": "Errore",
        "info_title": "Info",
        "unavailable": "Elemento non più disponibile.",
        "win_settings": "Clipboard Bridge - Impostazioni",
        "lbl_ip": "IP server",
        "lbl_port": "Porta",
        "lbl_token": "Token (vuoto = nessuno)",
        "lbl_user": "Account (vuoto = condiviso)",
        "lbl_pass": "Password account",
        "lbl_interval": "Intervallo controllo appunti (s)",
        "lbl_hk_send": "Hotkey invio",
        "lbl_hk_recv": "Hotkey ricezione",
        "hint_hk": "(es. ctrl+alt+c  ·  ctrl+shift+v)",
        "chk_autosync": "Sincronizzazione automatica",
        "chk_auto_files": "Scarica automaticamente i nuovi file",
        "chk_monitor": "Registra la cronologia locale",
        "chk_hotkeys": "Scorciatoie da tastiera attive",
        "err_numbers": "Porta e intervallo devono essere numeri interi.",
        "save": "Salva",
        "cancel": "Annulla",
    },
}


def t(key, **kw):
    lang = config.get("lang", "en") if "config" in globals() else "en"
    table = STRINGS.get(lang, STRINGS["en"])
    text = table.get(key) or STRINGS["en"].get(key, key)
    return text.format(**kw) if kw else text


# ---------------------------------------------------------------- config
def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    else:
        save_config(cfg)

    # Recover a legacy configuration even when 2.0.1 has already created an
    # empty default config in LocalAppData. Explicit settings made after that
    # installation always take precedence over the recovered values.
    if cfg.get("_legacy_migration_version", 0) < 2:
        legacy_path = _newest_existing(
            [os.path.join(DATA_DIR, "config.legacy.json")]
            + [os.path.join(root, "config.json") for root in _legacy_roots()]
        )
        if legacy_path and os.path.normcase(os.path.abspath(legacy_path)) != os.path.normcase(
                os.path.abspath(CONFIG_FILE)):
            try:
                with open(legacy_path, "r", encoding="utf-8") as f:
                    legacy = json.load(f)
                if isinstance(legacy, dict):
                    connection_keys = (
                        "mode", "server_ip", "server_port", "host_port",
                        "token", "username", "password",
                    )
                    connection_is_default = all(
                        cfg.get(key, DEFAULT_CONFIG[key]) == DEFAULT_CONFIG[key]
                        for key in connection_keys
                    )
                    if connection_is_default:
                        merged = dict(DEFAULT_CONFIG)
                        merged.update(legacy)
                        for key, value in cfg.items():
                            if key not in DEFAULT_CONFIG or value != DEFAULT_CONFIG[key]:
                                merged[key] = value
                        cfg = merged
                cfg["_legacy_migration_version"] = 2
                save_config(cfg)
            except (json.JSONDecodeError, OSError):
                pass
    return cfg


def save_config(cfg):
    os.makedirs(DATA_DIR, exist_ok=True)
    temp = CONFIG_FILE + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(temp, CONFIG_FILE)


config = load_config()


def server_url():
    # In server mode the client talks to its own embedded server on localhost.
    if config.get("mode") == "server":
        return f"http://127.0.0.1:{config.get('host_port', 5088)}"
    return f"http://{config['server_ip']}:{config['server_port']}"


def auth_headers():
    return {"X-Auth-Token": config["token"]} if config.get("token") else {}


def auth_params(extra=None):
    # When a server account is configured, append ?user=&password= so the
    # server routes the request to that account (ignored by the shared space
    # and by the built-in server). Optionally merge extra query params.
    p = dict(extra) if extra else {}
    user = config.get("username", "").strip()
    if user:
        p["user"] = user
        p["password"] = config.get("password", "")
    return p


def _set_connection_state(state):
    global _connection_state
    with _connection_lock:
        changed = _connection_state != state
        _connection_state = state
    if changed and _icon is not None:
        try:
            _icon.title = "Clipboard Bridge - " + (
                "CONNECTED" if state == "connected" else "NOT CONNECTED"
            )
            _icon.update_menu()
        except Exception:
            pass


def connection_status_text():
    with _connection_lock:
        state = _connection_state
    if state == "connected":
        return t("status_connected", server=server_url())
    if state == "auth":
        return t("status_auth")
    if state == "offline":
        return t("status_offline")
    return t("status_checking")


def check_connection():
    """Verify both server reachability and credentials for the selected space."""
    _set_connection_state("checking")
    try:
        response = requests.get(
            f"{server_url()}/clipboard/history",
            params=auth_params({"limit": 1}),
            headers=auth_headers(),
            timeout=4,
        )
        if response.status_code in (401, 403):
            _set_connection_state("auth")
            return False
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or "items" not in payload:
            raise ValueError("unexpected server response")
        _set_connection_state("connected")
        return True
    except Exception:
        _set_connection_state("offline")
        return False


def action_check_connection(icon=None, item=None):
    def work():
        if check_connection():
            notify(t("connected_notice", server=server_url()))
        else:
            notify(connection_status_text())
    _run_bg(work)


def notify(message, action=None):
    global _notification_action
    with _notification_lock:
        _notification_action = action
    if _icon is not None:
        try:
            _icon.notify(message, "Clipboard Bridge")
            return
        except Exception:
            pass
    print("[Clipboard Bridge]", message)


def apply_window_icon(win):
    try:
        if os.path.exists(ICON_PATH):
            win.iconbitmap(ICON_PATH)
    except Exception:
        pass


# ---------------------------------------------------------------- clipboard: text
def get_clipboard_text():
    try:
        return pyperclip.paste()
    except Exception:
        return ""


def set_clipboard_text(text):
    pyperclip.copy(text)


# ---------------------------------------------------------------- clipboard: files / images
def get_clipboard_files():
    """Return the list of files copied in File Explorer, or None."""
    try:
        data = ImageGrab.grabclipboard()
    except Exception:
        return None
    if isinstance(data, list):
        paths = [p for p in data if isinstance(p, str) and os.path.isfile(p)]
        return paths or None
    return None


class _DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("fNC", wintypes.BOOL),
        ("fWide", wintypes.BOOL),
    ]


def _build_hdrop(paths):
    """Build the CF_HDROP payload used by File Explorer for copied files."""
    normalized = [os.path.abspath(path) for path in paths]
    names = ("\0".join(normalized) + "\0\0").encode("utf-16-le")
    header = _DROPFILES()
    header.pFiles = ctypes.sizeof(_DROPFILES)
    header.fWide = True
    return ctypes.string_at(ctypes.byref(header), ctypes.sizeof(header)) + names


def set_clipboard_files(paths):
    """Put existing files on the Windows clipboard as a File Explorer copy."""
    files = [os.path.abspath(path) for path in paths if os.path.isfile(path)]
    if not files:
        raise ValueError("no existing files to copy")
    data = _build_hdrop(files)

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p

    for _ in range(10):
        if user32.OpenClipboard(0):
            break
        time.sleep(0.05)
    else:
        raise OSError("cannot open the clipboard")

    handle = kernel32.GlobalAlloc(0x0002, len(data))
    if not handle:
        user32.CloseClipboard()
        raise MemoryError("cannot allocate clipboard memory")
    transferred = False
    try:
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            raise OSError("cannot lock clipboard memory")
        ctypes.memmove(pointer, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.EmptyClipboard():
            raise OSError("cannot clear the clipboard")
        if not user32.SetClipboardData(15, handle):  # 15 = CF_HDROP
            raise OSError("cannot set file clipboard data")
        transferred = True
    finally:
        user32.CloseClipboard()
        if not transferred:
            kernel32.GlobalFree(handle)


def get_clipboard_image():
    """Return a bitmap image from the clipboard (e.g. a screenshot), or None."""
    try:
        data = ImageGrab.grabclipboard()
    except Exception:
        return None
    return data if isinstance(data, Image.Image) else None


def set_clipboard_image(img):
    """Put an image on the Windows clipboard using the CF_DIB format."""
    out = io.BytesIO()
    img.convert("RGB").save(out, "BMP")
    data = out.getvalue()[14:]  # skip the BMP file header
    out.close()

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p

    if not user32.OpenClipboard(0):
        raise OSError("cannot open the clipboard")
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(0x0002, len(data))
        lp = kernel32.GlobalLock(h)
        ctypes.memmove(lp, data, len(data))
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(8, h)  # 8 = CF_DIB
    finally:
        user32.CloseClipboard()


def image_to_png(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _img_hash(img):
    try:
        return hashlib.md5(img.tobytes()).hexdigest()
    except Exception:
        return None


def save_received(filename, raw):
    os.makedirs(RECEIVED_DIR, exist_ok=True)
    name = os.path.basename(str(filename or "file.bin").replace("\\", "/"))
    name = "".join("_" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in name)
    name = name.strip(" .") or "file.bin"
    stem, ext = os.path.splitext(name)
    if stem.upper() in {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    }:
        name = "_" + name
        stem, ext = os.path.splitext(name)
    dest = os.path.join(RECEIVED_DIR, name)
    i = 1
    while os.path.exists(dest):
        dest = os.path.join(RECEIVED_DIR, f"{stem} ({i}){ext}")
        i += 1
    with open(dest, "wb") as f:
        f.write(raw)
    return dest


def reveal_received_file(path):
    os.makedirs(RECEIVED_DIR, exist_ok=True)
    try:
        if os.path.isfile(path):
            subprocess.Popen(["explorer.exe", "/select,", os.path.normpath(path)])
        else:
            os.startfile(RECEIVED_DIR)
    except Exception:
        try:
            os.startfile(RECEIVED_DIR)
        except Exception:
            pass


# ---------------------------------------------------------------- network
def push_text(text):
    r = requests.post(f"{server_url()}/clipboard/text",
                      json={"text": text}, headers=auth_headers(),
                      params=auth_params(), timeout=5)
    r.raise_for_status()


def push_bytes(filename, raw):
    payload = {"filename": filename, "data": base64.b64encode(raw).decode()}
    r = requests.post(f"{server_url()}/clipboard/file",
                      json=payload, headers=auth_headers(),
                      params=auth_params(), timeout=30)
    r.raise_for_status()
    try:
        return r.json().get("id")
    except (ValueError, AttributeError):
        return None


def push_file(path):
    with open(path, "rb") as f:
        return push_bytes(os.path.basename(path), f.read())


def push_image(img):
    return push_bytes("clipboard.png", image_to_png(img))


def pull_latest():
    r = requests.get(f"{server_url()}/clipboard/latest",
                     headers=auth_headers(), params=auth_params(), timeout=5)
    r.raise_for_status()
    return r.json()


def fetch_history(limit=100):
    r = requests.get(f"{server_url()}/clipboard/history",
                     params=auth_params({"limit": limit}), headers=auth_headers(), timeout=5)
    r.raise_for_status()
    return r.json().get("items", [])


def fetch_item(item_id):
    r = requests.get(f"{server_url()}/clipboard/item/{item_id}",
                     headers=auth_headers(), params=auth_params(), timeout=30)
    r.raise_for_status()
    return r.json()


def _sync_source_key():
    source = {
        "url": server_url(),
        "account": config.get("username", "").strip(),
    }
    return hashlib.sha256(
        json.dumps(source, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _load_sync_state():
    if os.path.exists(SYNC_STATE_FILE):
        try:
            with open(SYNC_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"sources": {}}


def _save_sync_state(state):
    os.makedirs(DATA_DIR, exist_ok=True)
    temp = SYNC_STATE_FILE + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(temp, SYNC_STATE_FILE)


def _mark_remote_file_seen(item_id):
    if not item_id:
        return
    with _sync_state_lock:
        state = _load_sync_state()
        sources = state.setdefault("sources", {})
        key = _sync_source_key()
        seen = sources.setdefault(key, [])
        if item_id not in seen:
            seen.insert(0, item_id)
        sources[key] = seen[:500]
        _save_sync_state(state)


def _auto_receive_remote_files():
    items = fetch_history(200)
    remote_files = [item for item in items if item.get("type") == "file" and item.get("id")]
    current_ids = [item["id"] for item in remote_files]
    key = _sync_source_key()

    with _sync_state_lock:
        state = _load_sync_state()
        sources = state.setdefault("sources", {})
        if key not in sources:
            # Establish a baseline on first use instead of downloading the
            # complete pre-existing server history.
            sources[key] = current_ids[:500]
            _save_sync_state(state)
            return []
        seen = set(sources.get(key, []))

    new_items = [item for item in reversed(remote_files) if item["id"] not in seen]
    received_paths = []
    for item in new_items:
        full = fetch_item(item["id"])
        if full.get("type") != "file" or not full.get("data"):
            _mark_remote_file_seen(item["id"])
            continue
        raw = base64.b64decode(full["data"])
        dest = save_received(full.get("filename", "file.bin"), raw)
        record_local_file(dest)
        _mark_remote_file_seen(item["id"])
        received_paths.append(dest)
        notify(
            t("file_arrived", name=os.path.basename(dest)),
            action=lambda path=dest: reveal_received_file(path),
        )
    if received_paths:
        set_clipboard_files(received_paths)
    return received_paths


# ---------------------------------------------------------------- embedded server (server mode)
# A minimal HTTP server (standard library only) so this PC can be the server itself,
# keeping the history and the latest item. No web interface, on purpose.
_host_lock = threading.Lock()
_host_server = None
_host_thread = None


def _host_load():
    if os.path.exists(HOST_INDEX):
        try:
            with open(HOST_INDEX, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _host_save(index):
    os.makedirs(HOST_ITEMS, exist_ok=True)
    with open(HOST_INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def _host_meta(e):
    return {k: e.get(k) for k in ("id", "type", "timestamp", "filename", "mime", "size", "preview")}


def _host_with_content(e):
    out = _host_meta(e)
    path = os.path.join(HOST_ITEMS, e["file"])
    if e["type"] == "text":
        with open(path, "r", encoding="utf-8") as f:
            out["text"] = f.read()
    else:
        with open(path, "rb") as f:
            out["data"] = base64.b64encode(f.read()).decode()
    return out


def _host_add(kind, payload, filename=None, mime=None):
    os.makedirs(HOST_ITEMS, exist_ok=True)
    iid = uuid.uuid4().hex[:12]
    if kind == "text":
        fn = iid + ".txt"
        with open(os.path.join(HOST_ITEMS, fn), "w", encoding="utf-8") as f:
            f.write(payload)
        entry = {"id": iid, "type": "text", "timestamp": _now(), "file": fn, "filename": None,
                 "mime": "text/plain", "size": len(payload.encode("utf-8")), "preview": payload[:140]}
    else:
        ext = os.path.splitext(filename or "")[1].lower() or (mimetypes.guess_extension(mime or "") or ".bin")
        fn = iid + ext
        with open(os.path.join(HOST_ITEMS, fn), "wb") as f:
            f.write(payload)
        if not mime:
            mime = mimetypes.guess_type(filename or fn)[0] or "application/octet-stream"
        entry = {"id": iid, "type": "image" if mime.startswith("image/") else "file",
                 "timestamp": _now(), "file": fn, "filename": filename or fn,
                 "mime": mime, "size": len(payload), "preview": filename or fn}
    with _host_lock:
        index = _host_load()
        index.insert(0, entry)
        while len(index) > config.get("max_local_history", 100):
            old = index.pop()
            try:
                os.remove(os.path.join(HOST_ITEMS, old["file"]))
            except OSError:
                pass
        _host_save(index)
    return entry


class _SrvHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # keep the console quiet

    def _send(self, code, body=b"", ctype="application/json", filename=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if filename:
            self.send_header("Content-Disposition", f'inline; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode("utf-8"))

    def _raw(self, e):
        path = os.path.join(HOST_ITEMS, e["file"])
        if e["type"] == "text":
            with open(path, "r", encoding="utf-8") as f:
                self._send(200, f.read().encode("utf-8"), "text/plain; charset=utf-8")
        else:
            with open(path, "rb") as f:
                self._send(200, f.read(), e.get("mime") or "application/octet-stream", e.get("filename"))

    def do_GET(self):
        try:
            path = self.path.split("?", 1)[0]
            index = _host_load()
            if path == "/health":
                return self._json({"status": "ok", "items": len(index)})
            if path == "/clipboard/latest":
                return self._json(_host_with_content(index[0]) if index else {"type": "empty"})
            if path == "/clipboard/latest/raw":
                return self._raw(index[0]) if index else self._send(200, b"", "text/plain; charset=utf-8")
            if path == "/clipboard/history":
                return self._json({"items": [_host_meta(e) for e in index], "count": len(index)})
            if path.startswith("/clipboard/item/"):
                e = next((x for x in index if x["id"] == path.split("/")[3]), None)
                if not e:
                    return self._json({"error": "not found"}, 404)
                return self._raw(e) if path.endswith("/raw") else self._json(_host_with_content(e))
            self._json({"error": "not found"}, 404)
        except Exception as ex:
            try:
                self._json({"error": str(ex)}, 500)
            except Exception:
                pass

    def do_POST(self):
        try:
            path = self.path.split("?", 1)[0]
            n = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(n) if n else b""
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if path == "/clipboard/text":
                e = _host_add("text", (json.loads(body or b"{}")).get("text", ""))
                return self._json({"status": "ok", "id": e["id"]})
            if path == "/clipboard/file":
                d = json.loads(body or b"{}")
                raw = base64.b64decode((d.get("data") or "").encode())
                e = _host_add("bin", raw, d.get("filename") or "file.bin")
                return self._json({"status": "ok", "id": e["id"]})
            if path in ("/clipboard", "/clipboard/image"):
                if ctype == "application/json":
                    d = json.loads(body or b"{}")
                    if d.get("data"):
                        e = _host_add("bin", base64.b64decode(d["data"].encode()),
                                      d.get("filename") or "clipboard", d.get("mime"))
                        return self._json({"status": "ok", "id": e["id"], "type": e["type"]})
                    e = _host_add("text", d.get("text", ""))
                    return self._json({"status": "ok", "id": e["id"], "type": "text"})
                if ctype.startswith("text/") or ctype in ("", "application/x-www-form-urlencoded"):
                    try:
                        e = _host_add("text", body.decode("utf-8"))
                        return self._json({"status": "ok", "id": e["id"], "type": "text"})
                    except UnicodeDecodeError:
                        pass
                fn = self.headers.get("X-Filename") or ("clipboard" + (mimetypes.guess_extension(ctype) or ".bin"))
                e = _host_add("bin", body, fn, ctype or None)
                return self._json({"status": "ok", "id": e["id"], "type": e["type"]})
            self._json({"error": "not found"}, 404)
        except Exception as ex:
            try:
                self._json({"error": str(ex)}, 500)
            except Exception:
                pass

    def do_DELETE(self):
        try:
            path = self.path.split("?", 1)[0]
            if path == "/clipboard/history":
                with _host_lock:
                    for e in _host_load():
                        try:
                            os.remove(os.path.join(HOST_ITEMS, e["file"]))
                        except OSError:
                            pass
                    _host_save([])
                return self._json({"status": "cleared"})
            if path.startswith("/clipboard/item/"):
                iid = path.split("/")[3]
                with _host_lock:
                    index = _host_load()
                    e = next((x for x in index if x["id"] == iid), None)
                    _host_save([x for x in index if x["id"] != iid])
                if e:
                    try:
                        os.remove(os.path.join(HOST_ITEMS, e["file"]))
                    except OSError:
                        pass
                return self._json({"status": "deleted"})
            self._json({"error": "not found"}, 404)
        except Exception as ex:
            try:
                self._json({"error": str(ex)}, 500)
            except Exception:
                pass


def _lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def server_address():
    return f"{_lan_ip()}:{config.get('host_port', 5088)}"


def start_host_server():
    global _host_server, _host_thread
    if _host_server is not None:
        return True
    try:
        _host_server = http.server.ThreadingHTTPServer(("0.0.0.0", int(config.get("host_port", 5088))),
                                                       _SrvHandler)
    except OSError as e:
        notify(t("server_err", e=e))
        _host_server = None
        return False
    _host_thread = threading.Thread(target=_host_server.serve_forever, daemon=True)
    _host_thread.start()
    return True


def stop_host_server():
    global _host_server, _host_thread
    if _host_server is not None:
        try:
            _host_server.shutdown()
            _host_server.server_close()
        except Exception:
            pass
    _host_server = None
    _host_thread = None


# ---------------------------------------------------------------- local history
def _local_load():
    if os.path.exists(LOCAL_INDEX):
        try:
            with open(LOCAL_INDEX, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _local_save(index):
    while len(index) > config.get("max_local_history", 100):
        old = index.pop()
        if old.get("file"):
            try:
                os.remove(os.path.join(LOCAL_DIR, old["file"]))
            except OSError:
                pass
    with open(LOCAL_INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def _now():
    import datetime
    return datetime.datetime.now().isoformat(timespec="seconds")


def record_local_text(text):
    index = _local_load()
    if index and index[0].get("type") == "text" and index[0].get("text") == text:
        return
    index.insert(0, {"type": "text", "timestamp": _now(),
                     "preview": text[:140], "text": text})
    _local_save(index)


def record_local_image(img):
    name = uuid.uuid4().hex[:12] + ".png"
    img.save(os.path.join(LOCAL_DIR, name))
    index = _local_load()
    index.insert(0, {"type": "image", "timestamp": _now(),
                     "preview": f"image {img.width}x{img.height}", "file": name})
    _local_save(index)


def record_local_file(path):
    index = _local_load()
    index.insert(0, {"type": "file", "timestamp": _now(),
                     "preview": os.path.basename(path), "path": path})
    _local_save(index)


# ---------------------------------------------------------------- actions
def action_send_clipboard(icon=None, item=None):
    try:
        files = get_clipboard_files()
        if files:
            for p in files:
                _mark_remote_file_seen(push_file(p))
                record_local_file(p)
            notify(t("files_sent", n=len(files)) if len(files) > 1 else t("file_sent"))
            return
        img = get_clipboard_image()
        if img is not None:
            push_image(img)
            record_local_image(img)
            notify(t("image_sent"))
            return
        text = get_clipboard_text()
        if text and text.strip():
            push_text(text)
            record_local_text(text)
            notify(t("text_sent"))
        else:
            notify(t("clip_empty"))
    except Exception as e:
        notify(t("send_err", e=e))


def action_get_latest(icon=None, item=None):
    try:
        data = pull_latest()
        kind = data.get("type")
        if kind == "text":
            set_clipboard_text(data.get("text", ""))
            notify(t("text_recv"))
        elif kind == "image":
            raw = base64.b64decode(data["data"])
            set_clipboard_image(Image.open(io.BytesIO(raw)))
            notify(t("image_recv"))
        elif kind == "file":
            raw = base64.b64decode(data["data"])
            dest = save_received(data.get("filename", "file.bin"), raw)
            set_clipboard_files([dest])
            record_local_file(dest)
            _mark_remote_file_seen(data.get("id"))
            notify(
                t("file_arrived", name=os.path.basename(dest)),
                action=lambda path=dest: reveal_received_file(path),
            )
        else:
            notify(t("no_items"))
    except Exception as e:
        notify(t("recv_err", e=e))


def action_send_file(icon=None, item=None):
    paths = filedialog.askopenfilenames(parent=_root, title=t("choose_files"))
    if not paths:
        return

    def work():
        try:
            for p in paths:
                _mark_remote_file_seen(push_file(p))
                record_local_file(p)
            notify(t("files_sent", n=len(paths)) if len(paths) > 1 else t("file_sent"))
        except Exception as e:
            notify(t("send_err", e=e))
    _run_bg(work)


def open_received_folder(icon=None, item=None):
    os.makedirs(RECEIVED_DIR, exist_ok=True)
    try:
        os.startfile(RECEIVED_DIR)
    except Exception:
        pass


# ---------------------------------------------------------------- monitor / sync
def sync_loop():
    last_text = last_img = last_files = last_server = None
    next_connection_check = 0
    while not stop_event.is_set():
        try:
            if time.monotonic() >= next_connection_check:
                check_connection()
                next_connection_check = time.monotonic() + 15

            if config.get("auto_receive_files", True):
                try:
                    received = _auto_receive_remote_files()
                    if received:
                        # The clipboard change came from the server. Treat it as
                        # already seen so auto-sync does not upload it again.
                        last_files = tuple(received)
                        last_text = last_img = None
                except Exception:
                    pass

            if config.get("monitor_clipboard") or config.get("auto_sync"):
                files = get_clipboard_files()
                if files:
                    key = tuple(files)
                    if key != last_files:
                        last_files, last_text, last_img = key, None, None
                        for p in files:
                            record_local_file(p)
                            if config.get("auto_sync"):
                                try:
                                    _mark_remote_file_seen(push_file(p))
                                except Exception:
                                    pass
                else:
                    img = get_clipboard_image()
                    if img is not None:
                        h = _img_hash(img)
                        if h and h != last_img:
                            last_img, last_text, last_files = h, None, None
                            record_local_image(img)
                            if config.get("auto_sync"):
                                try:
                                    push_image(img)
                                except Exception:
                                    pass
                    else:
                        text = get_clipboard_text()
                        if text and text != last_text:
                            last_text, last_img, last_files = text, None, None
                            record_local_text(text)
                            if config.get("auto_sync"):
                                try:
                                    push_text(text)
                                except Exception:
                                    pass

            if config.get("auto_sync"):
                try:
                    data = pull_latest()
                    sid = data.get("id")
                    if sid and sid != last_server:
                        last_server = sid
                        if data.get("type") == "text":
                            txt = data.get("text", "")
                            set_clipboard_text(txt)
                            last_text = txt
                        elif data.get("type") == "image":
                            raw = base64.b64decode(data["data"])
                            im = Image.open(io.BytesIO(raw))
                            set_clipboard_image(im)
                            rb = get_clipboard_image()
                            last_img = _img_hash(rb) if rb is not None else _img_hash(im)
                except Exception:
                    pass
        except Exception:
            pass
        stop_event.wait(config.get("poll_interval", 3))


# ---------------------------------------------------------------- history window
def open_history_window(icon=None, item=None):
    root = tk.Toplevel(_root)
    root.title(t("win_history"))
    root.geometry("620x440")
    apply_window_icon(root)

    # UI updates from worker threads are queued and applied on the Tk thread.
    ui_q = queue.Queue()

    def _pump():
        try:
            while True:
                ui_q.get_nowait()()
        except queue.Empty:
            pass
        except Exception:
            pass
        try:
            root.after(100, _pump)
        except Exception:
            pass

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=8)

    # ----- server tab -----
    tab_srv = ttk.Frame(nb)
    nb.add(tab_srv, text=t("tab_server"))
    srv_list = tk.Listbox(tab_srv)
    srv_list.pack(fill="both", expand=True, padx=4, pady=4)
    srv_items = []

    def _srv_fill(items):
        srv_list.delete(0, tk.END)
        srv_items.clear()
        for it in items:
            srv_items.append(it)
            srv_list.insert(tk.END, f"[{it['type']}] {it.get('timestamp','')}  {it.get('preview','')}")

    def srv_refresh():
        srv_list.delete(0, tk.END)
        srv_list.insert(tk.END, t("loading"))
        srv_items.clear()

        def work():
            try:
                items = fetch_history(100)
                ui_q.put(lambda: _srv_fill(items))
            except Exception as e:
                ui_q.put(lambda: srv_list.delete(0, tk.END))
                notify(t("recv_err", e=e))
        threading.Thread(target=work, daemon=True).start()

    def srv_use():
        sel = srv_list.curselection()
        if not sel or sel[0] >= len(srv_items):
            return
        it = srv_items[sel[0]]

        def work():
            try:
                full = fetch_item(it["id"])
                if full.get("type") == "text":
                    set_clipboard_text(full.get("text", "")); notify(t("copied"))
                elif full.get("type") == "image":
                    set_clipboard_image(Image.open(io.BytesIO(base64.b64decode(full["data"])))); notify(t("copied"))
                else:
                    dest = save_received(full.get("filename", "file.bin"), base64.b64decode(full["data"]))
                    set_clipboard_files([dest])
                    record_local_file(dest)
                    _mark_remote_file_seen(full.get("id"))
                    notify(
                        t("file_arrived", name=os.path.basename(dest)),
                        action=lambda path=dest: reveal_received_file(path),
                    )
            except Exception as e:
                notify(t("recv_err", e=e))
        threading.Thread(target=work, daemon=True).start()

    def srv_delete():
        sel = srv_list.curselection()
        if not sel or sel[0] >= len(srv_items):
            return
        item_id = srv_items[sel[0]]["id"]

        def work():
            try:
                requests.delete(f"{server_url()}/clipboard/item/{item_id}",
                                headers=auth_headers(), params=auth_params(), timeout=5)
                ui_q.put(srv_refresh)
            except Exception as e:
                notify(t("recv_err", e=e))
        threading.Thread(target=work, daemon=True).start()

    b = ttk.Frame(tab_srv)
    b.pack(fill="x", padx=4, pady=4)
    ttk.Button(b, text=t("refresh"), command=srv_refresh).pack(side="left")
    ttk.Button(b, text=t("use"), command=srv_use).pack(side="left", padx=4)
    ttk.Button(b, text=t("delete"), command=srv_delete).pack(side="left")

    # ----- local tab -----
    tab_loc = ttk.Frame(nb)
    nb.add(tab_loc, text=t("tab_local"))
    loc_list = tk.Listbox(tab_loc)
    loc_list.pack(fill="both", expand=True, padx=4, pady=4)
    loc_items = []

    def loc_refresh():
        loc_list.delete(0, tk.END)
        loc_items.clear()
        for it in _local_load():
            loc_items.append(it)
            loc_list.insert(tk.END, f"[{it['type']}] {it.get('timestamp','')}  {it.get('preview','')}")

    def loc_send():
        sel = loc_list.curselection()
        if not sel or sel[0] >= len(loc_items):
            return
        it = loc_items[sel[0]]

        def work():
            try:
                if it["type"] == "text":
                    push_text(it.get("text", ""))
                elif it["type"] == "image" and it.get("file"):
                    push_image(Image.open(os.path.join(LOCAL_DIR, it["file"])))
                elif it["type"] == "file" and it.get("path") and os.path.isfile(it["path"]):
                    _mark_remote_file_seen(push_file(it["path"]))
                else:
                    notify(t("unavailable")); return
                notify(t("sent_server"))
            except Exception as e:
                notify(t("send_err", e=e))
        threading.Thread(target=work, daemon=True).start()

    b2 = ttk.Frame(tab_loc)
    b2.pack(fill="x", padx=4, pady=4)
    ttk.Button(b2, text=t("refresh"), command=loc_refresh).pack(side="left")
    ttk.Button(b2, text=t("send_to_server"), command=loc_send).pack(side="left", padx=4)

    loc_refresh()
    root.after(0, srv_refresh)   # window draws first, then loads in background
    root.after(100, _pump)


# ---------------------------------------------------------------- settings window
def open_settings(icon=None, item=None):
    root = tk.Toplevel(_root)
    root.title(t("win_settings"))
    root.geometry("440x690")
    root.attributes("-topmost", True)
    apply_window_icon(root)

    frm = ttk.Frame(root, padding=16)
    frm.pack(fill="both", expand=True)

    fields = [
        (t("lbl_ip"), "server_ip"),
        (t("lbl_port"), "server_port"),
        (t("lbl_host_port"), "host_port"),
        (t("lbl_token"), "token"),
        (t("lbl_user"), "username"),
        (t("lbl_pass"), "password"),
        (t("lbl_interval"), "poll_interval"),
        (t("lbl_hk_send"), "hotkey_send"),
        (t("lbl_hk_recv"), "hotkey_receive"),
    ]
    entries = {}
    for i, (label, key) in enumerate(fields):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=5)
        var = tk.StringVar(value=str(config.get(key, "")))
        ttk.Entry(frm, textvariable=var, width=20,
                  show="*" if key == "password" else "").grid(row=i, column=1, pady=5, sticky="e")
        entries[key] = var

    ttk.Label(frm, text=t("hint_hk"), foreground="#6b7280").grid(
        row=len(fields), column=0, columnspan=2, sticky="w")

    auto = tk.BooleanVar(value=config.get("auto_sync", False))
    auto_files = tk.BooleanVar(value=config.get("auto_receive_files", True))
    mon = tk.BooleanVar(value=config.get("monitor_clipboard", True))
    hk = tk.BooleanVar(value=config.get("hotkeys_enabled", True))
    base = len(fields) + 1
    ttk.Checkbutton(frm, text=t("chk_autosync"),
                    variable=auto).grid(row=base, column=0, columnspan=2, sticky="w", pady=3)
    ttk.Checkbutton(frm, text=t("chk_auto_files"),
                    variable=auto_files).grid(row=base + 1, column=0, columnspan=2, sticky="w", pady=3)
    ttk.Checkbutton(frm, text=t("chk_monitor"),
                    variable=mon).grid(row=base + 2, column=0, columnspan=2, sticky="w", pady=3)
    ttk.Checkbutton(frm, text=t("chk_hotkeys"),
                    variable=hk).grid(row=base + 3, column=0, columnspan=2, sticky="w", pady=3)

    status_frame = ttk.Frame(frm)
    status_frame.grid(row=base + 4, column=0, columnspan=2, sticky="ew", pady=(10, 2))
    status_label = ttk.Label(
        status_frame,
        text=connection_status_text(),
        font=("Segoe UI", 9, "bold"),
        wraplength=230,
    )
    status_label.pack(side="left", fill="x", expand=True)

    def show_connection_status():
        try:
            exists = root.winfo_exists()
        except tk.TclError:
            return
        if not exists:
            return
        status_label.config(
            text=connection_status_text(),
            foreground="#15803d" if _connection_state == "connected"
            else "#b45309" if _connection_state == "checking"
            else "#b91c1c",
        )
        connection_button.config(state="normal")

    def test_connection():
        connection_button.config(state="disabled")
        _set_connection_state("checking")
        show_connection_status()

        def work():
            check_connection()
            _cmd_q.put(show_connection_status)
        threading.Thread(target=work, daemon=True).start()

    connection_button = ttk.Button(
        status_frame,
        text=t("check_connection"),
        command=test_connection,
    )
    connection_button.pack(side="right", padx=(8, 0))

    msg = ttk.Label(frm, text="", foreground="#b91c1c", wraplength=360)
    msg.grid(row=base + 5, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def save():
        try:
            port = int(entries["server_port"].get())
            host_port = int(entries["host_port"].get())
            interval = int(entries["poll_interval"].get())
        except ValueError:
            msg.config(text=t("err_numbers"))
            return
        old_host_port = config.get("host_port", 5088)
        config["server_ip"] = entries["server_ip"].get().strip()
        config["server_port"] = port
        config["host_port"] = host_port
        config["token"] = entries["token"].get().strip()
        config["username"] = entries["username"].get().strip()
        config["password"] = entries["password"].get()
        config["poll_interval"] = interval if interval > 0 else 3
        config["hotkey_send"] = entries["hotkey_send"].get().strip().lower() or "ctrl+alt+c"
        config["hotkey_receive"] = entries["hotkey_receive"].get().strip().lower() or "ctrl+alt+v"
        config["auto_sync"] = auto.get()
        config["auto_receive_files"] = auto_files.get()
        config["monitor_clipboard"] = mon.get()
        config["hotkeys_enabled"] = hk.get()
        save_config(config)
        if config["hotkeys_enabled"]:
            register_hotkeys()
        else:
            unregister_hotkeys()
        # if the server port changed while running as server, restart it
        if config.get("mode") == "server" and host_port != old_host_port:
            stop_host_server()
            start_host_server()
        if icon is not None:
            try:
                icon.update_menu()
            except Exception:
                pass
        root.destroy()
        notify(t("settings_saved"))
        _run_bg(check_connection)

    bar = ttk.Frame(frm)
    bar.grid(row=base + 6, column=0, columnspan=2, pady=16)
    ttk.Button(bar, text=t("save"), command=save).pack(side="left", padx=6)
    ttk.Button(bar, text=t("cancel"), command=root.destroy).pack(side="left")
    root.after(80, test_connection)


# ---------------------------------------------------------------- keyboard shortcuts
_hotkeys = []


def _run_bg(fn):
    threading.Thread(target=fn, daemon=True).start()


def _install_notification_click_handler(icon):
    """Open the received file location when a Windows tray notification is clicked."""
    try:
        for message_code, handler in list(icon._message_handlers.items()):
            if getattr(handler, "__name__", "") != "_on_notify":
                continue

            def on_notify(wparam, lparam, original=handler):
                # NIN_BALLOONUSERCLICK is WM_USER + 5 (0x405).
                if int(lparam) & 0xFFFF == 0x405:
                    global _notification_action
                    with _notification_lock:
                        action = _notification_action
                        _notification_action = None
                    if action is not None:
                        _run_bg(action)
                        return 0
                return original(wparam, lparam)

            icon._message_handlers[message_code] = on_notify
            break
    except Exception:
        pass


def unregister_hotkeys():
    if keyboard is None:
        return
    for h in _hotkeys:
        try:
            keyboard.remove_hotkey(h)
        except Exception:
            pass
    _hotkeys.clear()


def register_hotkeys():
    if keyboard is None or not config.get("hotkeys_enabled", True):
        return
    unregister_hotkeys()
    try:
        _hotkeys.append(keyboard.add_hotkey(config.get("hotkey_send", "ctrl+alt+c"),
                                            lambda: _run_bg(action_send_clipboard)))
        _hotkeys.append(keyboard.add_hotkey(config.get("hotkey_receive", "ctrl+alt+v"),
                                            lambda: _run_bg(action_get_latest)))
    except Exception as e:
        notify(t("hotkey_err", e=e))


# ---------------------------------------------------------------- menu toggles
def toggle_auto_sync(icon, item):
    config["auto_sync"] = not config.get("auto_sync", False)
    save_config(config)
    icon.update_menu()


def toggle_monitor(icon, item):
    config["monitor_clipboard"] = not config.get("monitor_clipboard", False)
    save_config(config)
    icon.update_menu()


def toggle_hotkeys(icon, item):
    if keyboard is None:
        notify(t("no_keyboard"))
        return
    config["hotkeys_enabled"] = not config.get("hotkeys_enabled", True)
    save_config(config)
    register_hotkeys() if config["hotkeys_enabled"] else unregister_hotkeys()
    icon.update_menu()


def _set_lang(code):
    def handler(icon, item):
        config["lang"] = code
        save_config(config)
        icon.update_menu()
    return handler


def _set_mode(new_mode):
    def handler(icon, item):
        if config.get("mode", "client") == new_mode:
            return
        config["mode"] = new_mode
        save_config(config)
        if new_mode == "server":
            if start_host_server():
                notify(t("server_on", addr=server_address()))
        else:
            stop_host_server()
            notify(t("client_on"))
        _set_connection_state("checking")
        _run_bg(check_connection)
        icon.update_menu()
    return handler


def copy_server_addr(icon=None, item=None):
    addr = "http://" + server_address()
    set_clipboard_text(addr)
    notify(t("addr_copied", addr=addr))


def do_exit(icon, item):
    stop_host_server()
    unregister_hotkeys()
    stop_event.set()
    icon.stop()
    try:
        _cmd_q.put(_root.quit)
    except Exception:
        pass


# ---------------------------------------------------------------- icon and menu
def create_tray_icon():
    if os.path.exists(ICON_PATH):
        return Image.open(ICON_PATH)
    img = Image.new("RGB", (64, 64), (30, 30, 30))
    d = ImageDraw.Draw(img)
    d.rectangle([14, 10, 50, 54], outline=(255, 255, 255), width=3)
    d.rectangle([24, 6, 40, 16], fill=(255, 255, 255))
    return img


def build_menu():
    return Menu(
        MenuItem(lambda i: connection_status_text(), lambda icon, item: None, enabled=False),
        MenuItem(lambda i: t("check_connection"), action_check_connection),
        Menu.SEPARATOR,
        MenuItem(lambda i: t("send"), lambda icon, item: _run_bg(action_send_clipboard), default=True),
        MenuItem(lambda i: t("recv"), lambda icon, item: _run_bg(action_get_latest)),
        Menu.SEPARATOR,
        MenuItem(lambda i: t("send_file"), lambda icon, item: _cmd_q.put(action_send_file)),
        MenuItem(lambda i: t("open_recv"), open_received_folder),
        Menu.SEPARATOR,
        MenuItem(lambda i: t("history"), lambda icon, item: _cmd_q.put(open_history_window)),
        MenuItem(lambda i: t("autosync"), toggle_auto_sync,
                 checked=lambda i: config.get("auto_sync", False)),
        MenuItem(lambda i: t("monitor"), toggle_monitor,
                 checked=lambda i: config.get("monitor_clipboard", False)),
        MenuItem(lambda i: t("hotkeys"), toggle_hotkeys,
                 checked=lambda i: config.get("hotkeys_enabled", True)),
        MenuItem(lambda i: t("language"), Menu(
            MenuItem("English", _set_lang("en"),
                     checked=lambda i: config.get("lang", "en") == "en", radio=True),
            MenuItem("Italiano", _set_lang("it"),
                     checked=lambda i: config.get("lang", "en") == "it", radio=True),
        )),
        MenuItem(lambda i: t("mode"), Menu(
            MenuItem(lambda i: t("mode_client"), _set_mode("client"),
                     checked=lambda i: config.get("mode", "client") == "client", radio=True),
            MenuItem(lambda i: t("mode_server"), _set_mode("server"),
                     checked=lambda i: config.get("mode", "client") == "server", radio=True),
        )),
        MenuItem(lambda i: t("server_addr", addr=server_address()), copy_server_addr,
                 visible=lambda i: config.get("mode", "client") == "server"),
        Menu.SEPARATOR,
        MenuItem(lambda i: t("settings"), lambda icon, item: _cmd_q.put(open_settings)),
        MenuItem(lambda i: t("exit"), do_exit),
    )


def _set_app_id():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ClipboardBridge.Client")
    except Exception:
        pass


def _log_crash(exc):
    try:
        import traceback
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n--- {_now()} ---\n")
            f.write("".join(traceback.format_exception(exc)))
    except Exception:
        pass


def _tk_poll():
    # Runs on the Tk main thread: executes GUI commands queued by the tray thread.
    try:
        while True:
            _cmd_q.get_nowait()()
    except queue.Empty:
        pass
    except Exception as e:
        _log_crash(e)
    try:
        _root.after(120, _tk_poll)
    except Exception:
        pass


def main():
    global _icon, _root
    _set_app_id()
    # Tkinter owns the main thread (windows behave like normal Windows windows).
    _root = tk.Tk()
    _root.withdraw()
    if config.get("mode") == "server":
        start_host_server()
    threading.Thread(target=sync_loop, daemon=True).start()
    register_hotkeys()
    _icon = Icon("Clipboard Bridge", create_tray_icon(), "Clipboard Bridge", build_menu())
    _install_notification_click_handler(_icon)
    # pystray runs on its own thread; it asks the Tk thread to open windows via _cmd_q.
    threading.Thread(target=_icon.run, daemon=True).start()
    _root.after(120, _tk_poll)
    _root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _log_crash(e)
        raise
