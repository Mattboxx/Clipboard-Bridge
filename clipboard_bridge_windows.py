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
import re
import queue
import socket
import mimetypes
import threading
import http.server
import ctypes
import shutil
import subprocess
import time
import zipfile
import webbrowser
from contextlib import contextmanager
from functools import wraps
from ctypes import wintypes
from email.message import Message
from email.parser import BytesParser
from email.policy import default as email_policy
from urllib.parse import parse_qs, quote, unquote

import requests
import pyperclip
from PIL import Image, ImageGrab, ImageDraw, ImageTk, ImageFont
from pystray import Icon, MenuItem, Menu
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import font as tkfont

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
VERSION_PATH = os.path.join(RES_DIR, "VERSION")


def _read_app_version():
    try:
        with open(VERSION_PATH, "r", encoding="ascii") as version_file:
            version = version_file.read().strip()
        if re.fullmatch(r"\d+\.\d+\.\d+", version):
            return version
    except OSError:
        pass
    return "development"


APP_VERSION = _read_app_version()


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
    "appearance": "dark",
    "mode": "client",          # "client" = connect to an external server; "server" = be the server
    "server_ip": "127.0.0.1",  # external server address (client mode)
    "server_port": 5088,
    "host_port": 5088,         # port this PC listens on in server mode
    "host_max_upload_mb": 256, # compressed and expanded limit for local server uploads
    "token": "",
    "username": "",            # server account name (empty = shared space)
    "password": "",            # server account password
    "auto_sync": False,
    "auto_receive_files": True,
    "monitor_clipboard": True,
    "notifications_enabled": True,
    "notify_text": True,
    "notify_images": True,
    "notify_files": True,
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
_remote_activity_lock = threading.RLock()
_remote_request_context = threading.local()
_local_history_lock = threading.RLock()
_local_upload_lock = threading.Lock()
_local_upload_marker = None
_connection_lock = threading.Lock()
_connection_state = "checking"
_connection_checked_server = None
_connection_check_generation = 0
_instance_mutex = None

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
        "status_connected_short": "Connection: CONNECTED",
        "status_offline": "Connection: NOT CONNECTED",
        "status_auth": "Connection: SERVER FOUND, LOGIN REJECTED",
        "status_checking": "Connection: checking...",
        "tray_connected": "🟢 Connected",
        "tray_disconnected": "🔴 Disconnected",
        "check_connection": "Check connection now",
        "connected_notice": "Connected to {server}",
        "tab_general": "General",
        "tab_connection": "Connection",
        "tab_automation": "Automation",
        "tab_shortcuts": "Shortcuts",
        "section_notifications": "Notifications",
        "section_mode": "Operating mode",
        "section_application": "Application",
        "section_server": "Server address",
        "section_account": "Authentication",
        "section_status": "Connection status",
        "server_addr": "Server: {addr}  (click to copy)",
        "addr_copied": "Address copied: {addr}",
        "server_err": "Cannot start server: {e}",
        "lbl_host_port": "Server port (server mode)",
        "settings": "Settings…",
        "version_label": "Version {version}",
        "exit": "Exit",
        "image_sent": "Image sent",
        "file_sent": "File sent",
        "files_sent": "{n} files sent",
        "text_sent": "Text sent",
        "clip_empty": "Clipboard is empty",
        "send_err": "Send error: {e}",
        "text_recv": "Text copied to the clipboard",
        "image_recv": "Image copied to the clipboard",
        "text_arrived": "New text received and copied to the clipboard",
        "image_arrived": "New image received and copied to the clipboard",
        "file_saved": "File saved: {name}",
        "file_arrived": "New file received: {name}\nClick to show it in the folder.",
        "files_arrived": "{n} new files received.\nClick to open their folder.",
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
        "tab_local": "This PC",
        "refresh": "Refresh",
        "history_search": "Search previews and filenames",
        "all_types": "All types", "text_type": "Text", "image_type": "Images",
        "file_type": "Files", "bundle_type": "File groups",
        "previous": "Previous", "next": "Next",
        "history_results": "{shown} shown / {total} results",
        "history_error": "Could not load history. Check the connection and refresh.",
        "column_content": "Content", "column_type": "Type", "column_date": "Date",
        "column_size": "Size", "preview": "Preview", "preview_empty": "No item selected",
        "send_now": "Send clipboard", "receive_now": "Receive latest",
        "confirm_delete": "Delete this item from server history?",
        "copy_selected": "Copy", "search_history": "Search history",
        "no_results": "No matching items", "show_preview": "Preview",
        "send_short": "Send", "receive_short": "Receive",
        "lbl_appearance": "Appearance", "light_theme": "Light", "dark_theme": "Dark",
        "support": "Support on Ko-fi",
        "support_note": "If Clipboard Bridge is useful to you, a donation helps with maintenance and updates. Thank you for choosing to support the project!",
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
        "lbl_language": "Interface language",
        "lbl_history_limit": "Local history items",
        "lbl_interval": "Clipboard check interval (s)",
        "lbl_hk_send": "Send hotkey",
        "lbl_hk_recv": "Receive hotkey",
        "hint_hk": "(e.g. ctrl+alt+c  ·  ctrl+shift+v)",
        "chk_autosync": "Automatic synchronization",
        "chk_auto_files": "Automatically download new files",
        "chk_monitor": "Record local history",
        "chk_notifications": "Enable notifications",
        "chk_notify_text": "Text received",
        "chk_notify_images": "Images received",
        "chk_notify_files": "Files received",
        "chk_hotkeys": "Keyboard shortcuts enabled",
        "err_numbers": "Port, interval and history limit must be whole numbers.",
        "err_ports": "Ports must be between 1 and 65535.",
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
        "status_connected_short": "Connessione: COLLEGATO",
        "status_offline": "Connessione: NON COLLEGATO",
        "status_auth": "Connessione: SERVER TROVATO, ACCESSO RIFIUTATO",
        "status_checking": "Connessione: verifica in corso...",
        "tray_connected": "🟢 Connesso",
        "tray_disconnected": "🔴 Disconnesso",
        "check_connection": "Verifica connessione ora",
        "connected_notice": "Collegato a {server}",
        "tab_general": "Generale",
        "tab_connection": "Connessione",
        "tab_automation": "Automazione",
        "tab_shortcuts": "Scorciatoie",
        "section_notifications": "Notifiche",
        "section_mode": "Modalità operativa",
        "section_application": "Applicazione",
        "section_server": "Indirizzo server",
        "section_account": "Autenticazione",
        "section_status": "Stato connessione",
        "server_addr": "Server: {addr}  (clic per copiare)",
        "addr_copied": "Indirizzo copiato: {addr}",
        "server_err": "Impossibile avviare il server: {e}",
        "lbl_host_port": "Porta server (modalità server)",
        "settings": "Impostazioni…",
        "version_label": "Versione {version}",
        "exit": "Esci",
        "image_sent": "Immagine inviata",
        "file_sent": "File inviato",
        "files_sent": "{n} file inviati",
        "text_sent": "Testo inviato",
        "clip_empty": "Appunti vuoti",
        "send_err": "Errore invio: {e}",
        "text_recv": "Testo ricevuto negli appunti",
        "image_recv": "Immagine ricevuta negli appunti",
        "text_arrived": "Nuovo testo ricevuto e copiato negli appunti",
        "image_arrived": "Nuova immagine ricevuta e copiata negli appunti",
        "file_saved": "File salvato: {name}",
        "file_arrived": "Nuovo file ricevuto: {name}\nClicca per mostrarlo nella cartella.",
        "files_arrived": "{n} nuovi file ricevuti.\nClicca per aprire la cartella.",
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
        "tab_local": "Questo PC",
        "refresh": "Aggiorna",
        "history_search": "Cerca nelle anteprime e nei nomi dei file",
        "all_types": "Tutti i tipi", "text_type": "Testo", "image_type": "Immagini",
        "file_type": "File", "bundle_type": "Gruppi di file",
        "previous": "Precedenti", "next": "Successivi",
        "history_results": "{shown} visualizzati / {total} risultati",
        "history_error": "Cronologia non disponibile. Controlla la connessione e aggiorna.",
        "column_content": "Contenuto", "column_type": "Tipo", "column_date": "Data",
        "column_size": "Dimensione", "preview": "Anteprima", "preview_empty": "Nessun elemento selezionato",
        "send_now": "Invia appunti", "receive_now": "Ricevi ultimo",
        "confirm_delete": "Eliminare questo elemento dalla cronologia server?",
        "copy_selected": "Copia", "search_history": "Cerca nella cronologia",
        "no_results": "Nessun risultato", "show_preview": "Anteprima",
        "send_short": "Invia", "receive_short": "Ricevi",
        "lbl_appearance": "Aspetto", "light_theme": "Chiaro", "dark_theme": "Scuro",
        "support": "Supporta su Ko-fi",
        "support_note": "Se Clipboard Bridge ti è utile, una donazione aiuta a mantenere e aggiornare il progetto. Grazie di cuore se scegli di contribuire!",
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
        "lbl_language": "Lingua interfaccia",
        "lbl_history_limit": "Elementi cronologia locale",
        "lbl_interval": "Intervallo controllo appunti (s)",
        "lbl_hk_send": "Hotkey invio",
        "lbl_hk_recv": "Hotkey ricezione",
        "hint_hk": "(es. ctrl+alt+c  ·  ctrl+shift+v)",
        "chk_autosync": "Sincronizzazione automatica",
        "chk_auto_files": "Scarica automaticamente i nuovi file",
        "chk_monitor": "Registra la cronologia locale",
        "chk_notifications": "Abilita notifiche",
        "chk_notify_text": "Testo ricevuto",
        "chk_notify_images": "Immagini ricevute",
        "chk_notify_files": "File ricevuti",
        "chk_hotkeys": "Scorciatoie da tastiera attive",
        "err_numbers": "Porta, intervallo e limite cronologia devono essere numeri interi.",
        "err_ports": "Le porte devono essere comprese tra 1 e 65535.",
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
def _normalize_config(values):
    cfg = dict(values)
    for key, default in DEFAULT_CONFIG.items():
        value = cfg.get(key, default)
        if isinstance(default, bool) and not isinstance(value, bool):
            cfg[key] = default
        elif isinstance(default, str) and not isinstance(value, str):
            cfg[key] = default
    for key, minimum, maximum in (
        ("server_port", 1, 65535), ("host_port", 1, 65535),
        ("poll_interval", 1, 3600), ("max_local_history", 1, 100000),
        ("host_max_upload_mb", 1, 1024), ("_legacy_migration_version", 0, 2),
    ):
        default = DEFAULT_CONFIG.get(key, 0)
        try:
            number = int(cfg.get(key, default))
            cfg[key] = number if minimum <= number <= maximum else default
        except (TypeError, ValueError, OverflowError):
            cfg[key] = default
    if cfg.get("lang") not in ("en", "it"):
        cfg["lang"] = "en"
    if cfg.get("mode") not in ("client", "server"):
        cfg["mode"] = "client"
    if cfg.get("appearance") not in ("light", "dark"):
        cfg["appearance"] = "dark"
    return cfg


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                cfg.update(saved)
        except (json.JSONDecodeError, OSError):
            pass
    else:
        save_config(cfg)

    cfg = _normalize_config(cfg)
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
                        cfg = _normalize_config(merged)
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


def _request_settings():
    return getattr(_remote_request_context, "settings", config)


@contextmanager
def _remote_operation():
    with _remote_activity_lock:
        nested = hasattr(_remote_request_context, "settings")
        if not nested:
            _remote_request_context.settings = dict(config)
        try:
            yield
        finally:
            if not nested:
                del _remote_request_context.settings


def _in_remote_operation(function):
    @wraps(function)
    def call(*args, **kwargs):
        # A settings change must not reroute later members of an in-flight group.
        with _remote_operation():
            return function(*args, **kwargs)
    return call


def server_url():
    # In server mode the client talks to its own embedded server on localhost.
    values = _request_settings()
    if values.get("mode") == "server":
        return f"http://127.0.0.1:{values.get('host_port', 5088)}"
    return f"http://{values['server_ip']}:{values['server_port']}"


def auth_headers(settings=None):
    token = str((settings or _request_settings()).get("token", ""))
    return {"X-Auth-Token": token} if token and token.isascii() else {}


def auth_params(extra=None, settings=None):
    # When a server account is configured, append ?user=&password= so the
    # server routes the request to that account (ignored by the shared space
    # and by the built-in server). Optionally merge extra query params.
    p = dict(extra) if extra else {}
    values = settings or _request_settings()
    user = values.get("username", "").strip()
    if user:
        p["user"] = user
        p["password"] = values.get("password", "")
    token = str(values.get("token", ""))
    if token and not token.isascii():
        p["token"] = token  # query encoding supports secrets beyond HTTP's ASCII headers
    return p


def _set_connection_state(state, checked_server=None, generation=None):
    global _connection_state, _connection_checked_server, _connection_check_generation
    with _connection_lock:
        if generation is not None and generation != _connection_check_generation:
            return
        if generation is None and state == "checking":
            _connection_check_generation += 1
        changed = _connection_state != state
        _connection_state = state
        if checked_server:
            _connection_checked_server = checked_server
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
        checked_server = _connection_checked_server
    if state == "connected":
        return t("status_connected", server=checked_server or server_url())
    if state == "auth":
        return t("status_auth")
    if state == "offline":
        return t("status_offline")
    return t("status_checking")


def tray_connection_text():
    with _connection_lock:
        connected = _connection_state == "connected"
    return t("tray_connected" if connected else "tray_disconnected")


def settings_connection_status_text():
    with _connection_lock:
        connected = _connection_state == "connected"
    return t("status_connected_short") if connected else connection_status_text()


def check_connection(settings=None):
    """Verify both server reachability and credentials for the selected space."""
    global _connection_check_generation
    values = dict(settings or config)
    if values.get("mode") == "server":
        target = f"http://127.0.0.1:{values.get('host_port', 5088)}"
    else:
        target = f"http://{values.get('server_ip', '127.0.0.1')}:{values.get('server_port', 5088)}"

    params = auth_params({"limit": 1}, values)
    headers = auth_headers(values)

    with _connection_lock:
        _connection_check_generation += 1
        generation = _connection_check_generation
    _set_connection_state("checking", target, generation)
    try:
        response = requests.get(
            f"{target}/clipboard/history",
            params=params,
            headers=headers,
            timeout=4,
        )
        if response.status_code in (401, 403):
            _set_connection_state("auth", target, generation)
            return False
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or "items" not in payload:
            raise ValueError("unexpected server response")
        _set_connection_state("connected", target, generation)
        return True
    except Exception:
        _set_connection_state("offline", target, generation)
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
    if not config.get("notifications_enabled", True):
        with _notification_lock:
            _notification_action = None
        return
    with _notification_lock:
        _notification_action = action
    if _icon is not None:
        try:
            _icon.notify(message, "Clipboard Bridge")
            return
        except Exception:
            pass
    print("[Clipboard Bridge]", message)


def notify_received(kind, message, action=None):
    """Show a notification only when its received-content category is enabled."""
    setting = {
        "text": "notify_text",
        "image": "notify_images",
        "file": "notify_files",
    }.get(kind)
    if setting and not config.get(setting, True):
        return
    notify(message, action=action)


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


def _clipboard_sequence():
    try:
        return ctypes.windll.user32.GetClipboardSequenceNumber()
    except (AttributeError, OSError):
        return None


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
        rgb = img.convert("RGB")
        return hashlib.sha256(str(rgb.size).encode("ascii") + rgb.tobytes()).hexdigest()
    except Exception:
        return None


def _file_clipboard_key(paths):
    result = []
    for path in paths:
        path = os.path.normcase(os.path.abspath(path))
        try:
            info = os.stat(path)
            result.append((path, info.st_size, info.st_mtime_ns))
        except OSError:
            result.append((path, None, None))
    return tuple(result)


def _set_local_upload_marker(kind, value):
    global _local_upload_marker
    with _local_upload_lock:
        _local_upload_marker = (_sync_source_key(), kind, value)


def _take_local_upload_marker():
    global _local_upload_marker
    with _local_upload_lock:
        marker = _local_upload_marker
        _local_upload_marker = None
        return marker[1:] if marker and marker[0] == _sync_source_key() else None


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
    # Leave room for the download directory and collision suffix on Windows.
    budget = max(40, min(180, 240 - len(RECEIVED_DIR.encode("utf-16-le")) // 2))
    ext = ext.encode("utf-16-le")[:64].decode("utf-16-le", errors="ignore")
    stem_budget = max(8, budget - len(ext.encode("utf-16-le")) // 2 - 16)
    stem = stem.encode("utf-16-le")[:stem_budget * 2].decode("utf-16-le", errors="ignore")
    i = 0
    while True:
        suffix = f" ({i})" if i else ""
        dest = os.path.join(RECEIVED_DIR, f"{stem}{suffix}{ext}")
        try:
            stream = open(dest, "xb")
        except FileExistsError:
            i += 1
            continue
        try:
            with stream:
                stream.write(raw)
            return dest
        except Exception:
            try:
                os.remove(dest)
            except OSError:
                pass
            raise


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
@_in_remote_operation
def push_text(text):
    with _remote_activity_lock:
        r = requests.post(f"{server_url()}/clipboard/text",
                          json={"text": text}, headers=auth_headers(),
                          params=auth_params(), timeout=5)
        r.raise_for_status()
        try:
            item_id = r.json().get("id")
        except (ValueError, AttributeError):
            item_id = None
        _mark_local_item_sent(item_id)
        _set_local_upload_marker("text", text)
        return item_id


@_in_remote_operation
def push_bytes(filename, raw):
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with _remote_activity_lock:
        r = requests.post(
            f"{server_url()}/clipboard",
            files=[("files", (filename, raw, mime))],
            headers=auth_headers(),
            params=auth_params(),
            timeout=30,
        )
        r.raise_for_status()
        try:
            item_id = r.json().get("id")
        except (ValueError, AttributeError):
            item_id = None
        _mark_local_item_sent(item_id)
        return item_id


def push_file(path):
    return push_files([path])


@_in_remote_operation
def push_files(paths):
    paths = [os.path.abspath(path) for path in paths]
    if not paths:
        raise ValueError("No readable files selected")
    for path in paths:
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
    opened = []
    try:
        parts = []
        for path in paths:
            stream = open(path, "rb")
            opened.append(stream)
            mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
            parts.append(("files", (os.path.basename(path), stream, mime)))
        with _remote_activity_lock:
            r = requests.post(
                f"{server_url()}/clipboard",
                files=parts,
                headers=auth_headers(),
                params=auth_params(),
                timeout=120,
            )
            r.raise_for_status()
            item_id = r.json().get("id")
            _mark_local_item_sent(item_id, file_item=True)
            _set_local_upload_marker("files", _file_clipboard_key(paths))
            return item_id
    finally:
        for stream in opened:
            stream.close()


@_in_remote_operation
def push_image(img):
    with _remote_activity_lock:
        item_id = push_bytes("clipboard.png", image_to_png(img))
        _set_local_upload_marker("image", _img_hash(img))
        return item_id


@_in_remote_operation
def pull_latest():
    with _remote_activity_lock:
        r = requests.get(f"{server_url()}/clipboard/latest",
                         headers=auth_headers(), params=auth_params(), timeout=5)
        r.raise_for_status()
        return r.json()


@_in_remote_operation
def poll_latest(known_id):
    """Poll small metadata; download content only when the latest ID changes."""
    with _remote_activity_lock:
        r = requests.get(f"{server_url()}/clipboard/latest/meta",
                         headers=auth_headers(), params=auth_params(), timeout=5)
        if r.status_code in (404, 405):
            return pull_latest()  # compatibility with older servers
        r.raise_for_status()
        metadata = r.json()
        if (not metadata.get("id") or metadata["id"] == known_id
                or metadata.get("type") in ("file", "bundle")):
            return metadata
        return fetch_item(metadata["id"])


@_in_remote_operation
def fetch_history_page(limit=100, query="", kind="", offset=0):
    with _remote_activity_lock:
        r = requests.get(f"{server_url()}/clipboard/history",
                         params=auth_params({"limit": limit, "q": query, "type": kind, "offset": offset}),
                         headers=auth_headers(), timeout=5)
        r.raise_for_status()
        return r.json()


def fetch_history(limit=100):
    return fetch_history_page(limit).get("items", [])


@_in_remote_operation
def fetch_item(item_id):
    with _remote_activity_lock:
        r = requests.get(f"{server_url()}/clipboard/item/{item_id}",
                         headers=auth_headers(), params=auth_params(), timeout=30)
        r.raise_for_status()
        return r.json()


@_in_remote_operation
def fetch_bundle_member(item_id, member_index):
    with _remote_activity_lock:
        r = requests.get(
            f"{server_url()}/clipboard/item/{item_id}/file/{member_index}/raw",
            headers=auth_headers(),
            params=auth_params(),
            timeout=60,
        )
        r.raise_for_status()
        filename = r.headers.get("X-Clipboard-Filename", "file.bin")
        try:
            filename = unquote(filename)
        except Exception:
            pass
        return filename, r.content


@_in_remote_operation
def save_remote_files(item):
    with _remote_activity_lock:
        key, item_id = _sync_source_key(), item.get("id")
        with _sync_state_lock:
            saved = _load_sync_state().get("downloads", {}).get(key, {}).get(item_id, [])
        if saved and all(os.path.isfile(path) for path in saved):
            return saved
        paths = []
        try:
            if item.get("type") == "bundle":
                for member in item.get("files", []):
                    filename, raw = fetch_bundle_member(item_id, member.get("index", 0))
                    paths.append(save_received(member.get("filename") or filename, raw))
            elif item.get("type") == "file":
                if "data" in item:
                    raw = base64.b64decode(item["data"])
                else:
                    r = requests.get(f"{server_url()}/clipboard/item/{item_id}/raw",
                                     headers=auth_headers(), params=auth_params(), timeout=60)
                    r.raise_for_status()
                    raw = r.content
                paths.append(save_received(item.get("filename", "file.bin"), raw))
            if paths and item_id:
                with _sync_state_lock:
                    state = _load_sync_state()
                    downloads = state.setdefault("downloads", {}).setdefault(key, {})
                    downloads[item_id] = paths
                    state["downloads"][key] = dict(list(downloads.items())[-500:])
                    _save_sync_state(state)
            return paths
        except Exception:
            # An interrupted group must not leave half a group or duplicate files on retry.
            for path in paths:
                try:
                    os.remove(path)
                except OSError:
                    pass
            raise


def _sync_source_key():
    values = _request_settings()
    source = {
        "url": server_url(),
        "account": values.get("username", "").strip() if values.get("mode") != "server" else "",
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


def _remember_item(item_id, *, file_seen=False, suppress_notification=False, update_latest=True):
    if not item_id:
        return
    with _sync_state_lock:
        state = _load_sync_state()
        key = _sync_source_key()
        if update_latest:
            state.setdefault("latest_items", {})[key] = item_id
        if file_seen:
            sources = state.setdefault("sources", {})
            seen = sources.setdefault(key, [])
            if item_id not in seen:
                seen.insert(0, item_id)
            sources[key] = seen[:500]
        if suppress_notification:
            silent = state.setdefault("silent_items", {}).setdefault(key, [])
            if item_id not in silent:
                silent.insert(0, item_id)
            state["silent_items"][key] = silent[:500]
        _save_sync_state(state)


def _mark_remote_file_seen(item_id):
    _remember_item(item_id, file_seen=True, update_latest=False)


def _mark_local_item_sent(item_id, file_item=False):
    _remember_item(
        item_id,
        file_seen=file_item,
        suppress_notification=True,
    )


def _last_remembered_item():
    with _sync_state_lock:
        state = _load_sync_state()
        return state.get("latest_items", {}).get(_sync_source_key())


def _consume_silent_item(item_id):
    if not item_id:
        return False
    with _sync_state_lock:
        state = _load_sync_state()
        key = _sync_source_key()
        items = state.get("silent_items", {}).get(key, [])
        if item_id not in items:
            return False
        state["silent_items"][key] = [value for value in items if value != item_id]
        _save_sync_state(state)
        return True


@_in_remote_operation
def _auto_receive_remote_files():
    items = fetch_history(200)
    remote_files = [
        item for item in items
        if item.get("type") in ("file", "bundle") and item.get("id")
    ]
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
    latest = items[0] if items else {}
    clipboard_paths = []
    for item in new_items:
        paths = save_remote_files(item)
        if not paths:
            _mark_remote_file_seen(item["id"])
            continue
        record_local_files(paths)
        _mark_remote_file_seen(item["id"])
        if item["id"] == latest.get("id"):
            clipboard_paths = paths
        message = (
            t("files_arrived", n=len(paths)) if len(paths) > 1
            else t("file_arrived", name=os.path.basename(paths[0]))
        )
        notify_received(
            "file",
            message,
            action=(
                (lambda: open_received_folder()) if len(paths) > 1
                else (lambda path=paths[0]: reveal_received_file(path))
            ),
        )
    # Retry a busy clipboard using the saved files, without downloading/notifying twice.
    if latest.get("type") in ("file", "bundle") and latest.get("id") != _last_remembered_item():
        with _sync_state_lock:
            saved = _load_sync_state().get("downloads", {}).get(key, {}).get(latest["id"], [])
        if saved and all(os.path.isfile(path) for path in saved):
            clipboard_paths = saved
    if clipboard_paths:
        set_clipboard_files(clipboard_paths)
        _set_local_upload_marker("files", _file_clipboard_key(clipboard_paths))
        _remember_item(latest.get("id"))
    return clipboard_paths


# ---------------------------------------------------------------- embedded server (server mode)
# A minimal HTTP server (standard library only) so this PC can be the server itself,
# keeping the history and the latest item. No web interface, on purpose.
_host_lock = threading.Lock()
_host_server = None
_host_thread = None


def _filter_history(items, query="", kind=""):
    query = query.strip().casefold()
    result = []
    for item in items:
        if kind and item.get("type") != kind:
            continue
        names = " ".join(member.get("filename") or "" for member in item.get("files", []))
        names += " " + " ".join(os.path.basename(path) for path in item.get("paths", []))
        searchable = " ".join((item.get("preview") or "", item.get("filename") or "", names))
        if not query or query in searchable.casefold():
            result.append(item)
    return result


def _host_history_page(index, params):
    query = (params.get("q") or "").strip()
    kind = params.get("type") or ""
    if len(query) > 200 or kind not in ("", "text", "image", "file", "bundle"):
        raise ValueError("invalid history search or type")
    try:
        offset = int(params.get("offset", 0))
        limit = int(params["limit"]) if "limit" in params else None
    except (TypeError, ValueError):
        raise ValueError("invalid history limit or offset") from None
    if offset < 0 or (limit is not None and not 1 <= limit <= 1000):
        raise ValueError("history limit must be 1-1000 and offset must be nonnegative")
    filtered = _filter_history(index, query, kind)
    page = filtered[offset:offset + limit] if limit is not None else filtered[offset:]
    return {"items": [_host_meta(e) for e in page], "count": len(page), "total": len(filtered),
            "offset": offset, "has_more": offset + len(page) < len(filtered)}


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
    temp = HOST_INDEX + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    os.replace(temp, HOST_INDEX)


def _host_meta(e):
    out = {k: e.get(k) for k in ("id", "type", "timestamp", "filename", "mime", "size", "preview")}
    if e.get("type") == "bundle":
        out["file_count"] = len(e.get("files", []))
        out["files"] = [
            {
                "index": index,
                "filename": member.get("filename"),
                "mime": member.get("mime"),
                "size": member.get("size", 0),
                "type": member.get("type", "file"),
            }
            for index, member in enumerate(e.get("files", []))
        ]
    return out


def _host_with_content(e):
    out = _host_meta(e)
    if e["type"] == "bundle":
        return out
    path = os.path.join(HOST_ITEMS, e["file"])
    if e["type"] == "text":
        with open(path, "r", encoding="utf-8", newline="") as f:
            out["text"] = f.read()
    else:
        with open(path, "rb") as f:
            out["data"] = base64.b64encode(f.read()).decode()
    return out


def _host_clean_filename(filename):
    if filename is None:
        return None
    filename = str(filename).replace("\\", "/").rsplit("/", 1)[-1]
    filename = "".join(ch for ch in filename if ch >= " " and ch not in "\r\n\x7f").strip()
    return filename[:240] or None


def _host_mime(content_type):
    return (content_type or "").split(";", 1)[0].strip().lower()


def _host_header_filename(headers):
    for header in ("X-Filename", "X-File-Name", "X-Clipboard-Filename"):
        if headers.get(header):
            return _host_clean_filename(unquote(headers.get(header)))
    message = Message()
    message["Content-Disposition"] = headers.get("Content-Disposition", "")
    if message.get_filename():
        return _host_clean_filename(message.get_filename())
    message = Message()
    message["Content-Type"] = headers.get("Content-Type", "")
    return _host_clean_filename(message.get_param("name"))


def _host_decode_text(raw, content_type="", allow_legacy=False):
    message = Message()
    message["Content-Type"] = content_type
    candidates = []
    if message.get_content_charset():
        candidates.append(message.get_content_charset())
    if raw.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        candidates.append("utf-32")
    elif raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        candidates.append("utf-16")
    candidates.extend(("utf-8-sig", "utf-8"))
    if allow_legacy:
        candidates.append("latin-1")
    for encoding in candidates:
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return None


def _host_looks_like_text(raw, content_type=""):
    text = _host_decode_text(raw, content_type)
    return text is not None and all(ch.isprintable() or ch in "\r\n\t" for ch in text)


def _host_json_text(data):
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in ("text", "value", "content", "clipboard", "string"):
            if key in data:
                value = data[key]
                return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)


def _host_decode_base64(value):
    if not isinstance(value, str):
        return None, None
    encoded = value.strip()
    data_mime = None
    if encoded.lower().startswith("data:") and "," in encoded:
        header, encoded = encoded.split(",", 1)
        if ";base64" not in header.lower():
            return None, None
        data_mime = _host_mime(header[5:].split(";", 1)[0])
    encoded = re.sub(r"\s+", "", encoded)
    encoded += "=" * (-len(encoded) % 4)
    try:
        return base64.b64decode(encoded, altchars=b"-_", validate=True), data_mime
    except (ValueError, base64.binascii.Error):
        return None, None


def _host_multipart(body, content_type):
    """Return every uploaded file as one group, or the first text field."""
    prefix = (
        "Content-Type: " + content_type + "\r\n"
        "MIME-Version: 1.0\r\n\r\n"
    ).encode("utf-8")
    message = BytesParser(policy=email_policy).parsebytes(prefix + body)
    text_value = None
    uploads = []
    for part in message.iter_parts():
        filename = _host_clean_filename(part.get_filename())
        payload = part.get_payload(decode=True) or b""
        if filename is not None:
            uploads.append((payload, filename, part.get_content_type()))
            continue
        field = part.get_param("name", header="content-disposition")
        if field in ("text", "value", "content", "clipboard", "string") or text_value is None:
            text_value = _host_decode_text(
                payload,
                part.get("Content-Type", "text/plain"),
                allow_legacy=True,
            )
    if uploads:
        return "files", uploads, None, None
    return ("text", text_value, None, None) if text_value is not None else None


def _host_entry_files(entry):
    if entry.get("type") == "bundle":
        return [member.get("file") for member in entry.get("files", []) if member.get("file")]
    return [entry.get("file")] if entry.get("file") else []


def _host_delete_files(entry):
    for filename in _host_entry_files(entry):
        try:
            os.remove(os.path.join(HOST_ITEMS, filename))
        except OSError:
            pass


def _host_commit_entry(entry):
    with _host_lock:
        index = [entry] + _host_load()
        limit = config.get("max_local_history", 100)
        expired = index[limit:]
        try:
            _host_save(index[:limit])
        except Exception:
            _host_delete_files(entry)
            raise
        for old in expired:
            _host_delete_files(old)
    return entry


def _host_write_item(filename, payload):
    path = os.path.join(HOST_ITEMS, filename)
    try:
        with open(path, "wb") as stream:
            stream.write(payload)
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise


def _host_add(kind, payload, filename=None, mime=None):
    os.makedirs(HOST_ITEMS, exist_ok=True)
    iid = uuid.uuid4().hex[:12]
    if kind == "text":
        fn = iid + ".txt"
        _host_write_item(fn, payload.encode("utf-8"))
        entry = {"id": iid, "type": "text", "timestamp": _now(), "file": fn, "filename": None,
                 "mime": "text/plain", "size": len(payload.encode("utf-8")), "preview": payload[:140]}
    else:
        filename = _host_clean_filename(filename)
        mime = _host_mime(mime)
        candidate = os.path.splitext(filename or "")[1]
        ext = candidate.lower() if (
            len(candidate) <= 32 and re.fullmatch(r"\.[A-Za-z0-9._+-]+", candidate or "")
        ) else ""
        ext = ext or (mimetypes.guess_extension(mime or "") or ".bin")
        fn = iid + ext
        _host_write_item(fn, payload)
        if not mime:
            mime = mimetypes.guess_type(filename or fn)[0] or "application/octet-stream"
        entry = {"id": iid, "type": "image" if mime.startswith("image/") else "file",
                 "timestamp": _now(), "file": fn, "filename": filename or fn,
                 "mime": mime, "size": len(payload), "preview": filename or fn}
    return _host_commit_entry(entry)


def _host_add_bundle(uploads):
    if len(uploads) == 1:
        raw, filename, mime = uploads[0]
        return _host_add("bin", raw, filename, mime)
    os.makedirs(HOST_ITEMS, exist_ok=True)
    iid = uuid.uuid4().hex[:12]
    members = []
    try:
        for index, (raw, filename, mime) in enumerate(uploads):
            filename = _host_clean_filename(filename) or f"file-{index + 1}.bin"
            mime = _host_mime(mime) or mimetypes.guess_type(filename)[0] or "application/octet-stream"
            ext = os.path.splitext(filename)[1]
            ext = ext.lower() if len(ext) <= 32 and re.fullmatch(r"\.[A-Za-z0-9._+-]+", ext or "") else ".bin"
            stored = f"{iid}-{index}{ext}"
            _host_write_item(stored, raw)
            members.append({
                "file": stored,
                "filename": filename,
                "mime": mime,
                "size": len(raw),
                "type": "image" if mime.startswith("image/") else "file",
            })
    except Exception:
        _host_delete_files({"type": "bundle", "files": members})
        raise
    entry = {
        "id": iid,
        "type": "bundle",
        "timestamp": _now(),
        "filename": None,
        "mime": "application/zip",
        "size": sum(member["size"] for member in members),
        "preview": ", ".join(member["filename"] for member in members),
        "files": members,
    }
    return _host_commit_entry(entry)


def _host_bundle_bytes(entry):
    output = io.BytesIO()
    used = set()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, member in enumerate(entry.get("files", [])):
            name = _host_clean_filename(member.get("filename")) or f"file-{index + 1}.bin"
            original = name
            suffix = 2
            while name.lower() in used:
                stem, ext = os.path.splitext(original)
                name = f"{stem} ({suffix}){ext}"
                suffix += 1
            used.add(name.lower())
            archive.write(os.path.join(HOST_ITEMS, member["file"]), name)
    return output.getvalue()


def _host_uploads_from_zip(raw):
    if not raw:
        raise ValueError("empty archive")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = [
                info for info in archive.infolist()
                if not info.is_dir()
                and not info.filename.replace("\\", "/").startswith("__MACOSX/")
                and not info.filename.replace("\\", "/").endswith(".DS_Store")
            ]
            if not members:
                raise ValueError("archive contains no files")
            if len(members) > 500:
                raise ValueError("archive contains too many files")
            max_bytes = int(config.get("host_max_upload_mb", 256)) * 1024 * 1024
            if sum(info.file_size for info in members) > max_bytes:
                raise ValueError("expanded archive exceeds the upload limit")
            uploads = []
            expanded = 0
            for info in members:
                if info.flag_bits & 0x1:
                    raise ValueError("encrypted archives are not supported")
                filename = _host_clean_filename(info.filename) or "file.bin"
                chunks = []
                with archive.open(info) as source:
                    while True:
                        chunk = source.read(min(1024 * 1024, max_bytes - expanded + 1))
                        if not chunk:
                            break
                        expanded += len(chunk)
                        if expanded > max_bytes:
                            raise ValueError("expanded archive exceeds the upload limit")
                        chunks.append(chunk)
                uploads.append((
                    b"".join(chunks),
                    filename,
                    mimetypes.guess_type(filename)[0] or "application/octet-stream",
                ))
            return uploads
    except zipfile.BadZipFile as exc:
        raise ValueError("invalid ZIP archive") from exc


class _SrvHandler(http.server.BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, *a):
        pass  # keep the console quiet

    def _send(self, code, body=b"", ctype="application/json", filename=None, item=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if filename:
            fallback = "".join(
                ch for ch in filename if 32 <= ord(ch) < 127 and ch not in '"\\'
            ) or "download"
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{quote(filename, safe="")}',
            )
            self.send_header("X-Clipboard-Filename", quote(filename, safe=""))
        if item:
            self.send_header("X-Clipboard-Id", item["id"])
            self.send_header("X-Clipboard-Type", item["type"])
            if item.get("type") == "bundle":
                self.send_header("X-Clipboard-File-Count", str(len(item.get("files", []))))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode("utf-8"))

    def _raw(self, e):
        if e["type"] == "bundle":
            return dict(code=200, body=_host_bundle_bytes(e), ctype="application/zip",
                        filename=f"clipboard-{e['id']}.zip", item=e)
        path = os.path.join(HOST_ITEMS, e["file"])
        if e["type"] == "text":
            with open(path, "r", encoding="utf-8", newline="") as f:
                return dict(code=200, body=f.read().encode("utf-8"),
                            ctype="text/plain; charset=utf-8", item=e)
        else:
            with open(path, "rb") as f:
                return dict(code=200, body=f.read(),
                            ctype=e.get("mime") or "application/octet-stream",
                            filename=e.get("filename"), item=e)

    def _get_payload(self, path, index, params):
        if path == "/health":
            return {"status": "ok", "items": len(index)}
        if path == "/clipboard/latest":
            return _host_with_content(index[0]) if index else {"type": "empty"}
        if path == "/clipboard/latest/meta":
            return _host_meta(index[0]) if index else {"type": "empty"}
        if path in ("/clipboard/latest/raw", "/clipboard/raw"):
            return self._raw(index[0]) if index else dict(code=200, body=b"", ctype="text/plain; charset=utf-8")
        if path == "/clipboard/history":
            return _host_history_page(index, params)
        parts = path.strip("/").split("/")
        if len(parts) >= 3 and parts[:2] == ["clipboard", "item"]:
            e = next((x for x in index if x["id"] == parts[2]), None)
            if e:
                if len(parts) == 6 and parts[3] == "file" and parts[5] == "raw":
                    try:
                        member_index = int(parts[4])
                        if member_index < 0:
                            raise IndexError
                        member = e.get("files", [])[member_index]
                    except (ValueError, IndexError):
                        return dict(code=404, body=b'{"error":"not found"}')
                    with open(os.path.join(HOST_ITEMS, member["file"]), "rb") as stream:
                        return dict(code=200, body=stream.read(),
                                    ctype=member.get("mime") or "application/octet-stream",
                                    filename=member.get("filename"), item=e)
                if len(parts) == 4 and parts[3] == "raw":
                    return self._raw(e)
                if len(parts) == 3:
                    return _host_with_content(e)
        return dict(code=404, body=b'{"error":"not found"}')

    def do_GET(self):
        try:
            path, _, query = self.path.partition("?")
            params = {key: values[0] for key, values in parse_qs(query, keep_blank_values=True).items()}
            # Snapshot content under the store lock, then write to the socket outside it.
            with _host_lock:
                payload = self._get_payload(path, _host_load(), params)
            if "body" in payload:
                return self._send(**payload)
            return self._json(payload)
        except ValueError as ex:
            self._json({"error": str(ex)}, 400)
        except Exception as ex:
            try:
                self._json({"error": str(ex)}, 500)
            except Exception:
                pass

    def do_POST(self):
        try:
            path, _, query_string = self.path.partition("?")
            if self.headers.get("Transfer-Encoding"):
                self.close_connection = True
                return self._json({"error": "Transfer-Encoding is not supported; send Content-Length"}, 501)
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or not re.fullmatch(r"[0-9]+", lengths[0].strip()):
                self.close_connection = True
                return self._json({"error": "invalid or missing Content-Length"}, 400)
            n = int(lengths[0])
            max_request = int(config.get("host_max_upload_mb", 256)) * 1024 * 1024
            if n > max_request:
                self.close_connection = True
                return self._json({"error": "upload exceeds the server limit"}, 413)
            try:
                body = self.rfile.read(n) if n else b""
            except socket.timeout:
                self.close_connection = True
                return self._json({"error": "upload timed out"}, 408)
            if len(body) != n:
                self.close_connection = True
                return self._json({"error": "incomplete request body"}, 400)
            content_type = self.headers.get("Content-Type") or ""
            ctype = _host_mime(content_type)
            filename = _host_header_filename(self.headers)
            if filename is None and query_string:
                query = parse_qs(query_string, keep_blank_values=True)
                for key in ("filename", "file_name", "name"):
                    value = query.get(key, [""])[0]
                    if value:
                        filename = _host_clean_filename(value)
                        break
            multipart = (
                _host_multipart(body, content_type)
                if ctype == "multipart/form-data"
                else None
            )

            if path == "/clipboard/bundle":
                try:
                    e = _host_add_bundle(_host_uploads_from_zip(body))
                except ValueError as error:
                    return self._json({"error": str(error)}, 400)
                return self._json({
                    "status": "ok",
                    "id": e["id"],
                    "type": e["type"],
                    "file_count": len(e.get("files", [])) or 1,
                })

            if path == "/clipboard/text":
                if ctype == "application/json":
                    try:
                        text = _host_json_text(json.loads(body.decode("utf-8-sig")))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        return self._json({"error": "invalid JSON"}, 400)
                elif ctype == "application/x-www-form-urlencoded":
                    form = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
                    key = next((k for k in ("text", "value", "content", "clipboard", "string") if k in form), None)
                    text = form[key][0] if key else (next(iter(form.values()))[0] if form else "")
                else:
                    text = _host_decode_text(body, content_type, allow_legacy=True)
                    if text is None:
                        return self._json({"error": "invalid text encoding"}, 400)
                e = _host_add("text", text)
                return self._json({"status": "ok", "id": e["id"]})

            if path == "/clipboard/file":
                raw = body
                mime = ctype or None
                if multipart and multipart[0] == "files":
                    e = _host_add_bundle(multipart[1])
                    return self._json({
                        "status": "ok",
                        "id": e["id"],
                        "type": e["type"],
                        "file_count": len(e.get("files", [])) or 1,
                    })
                elif ctype == "application/json" and filename is None:
                    try:
                        data = json.loads(body.decode("utf-8-sig"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        return self._json({"error": "invalid JSON"}, 400)
                    if not isinstance(data, dict) or "data" not in data:
                        return self._json({"error": "file data missing"}, 400)
                    raw, data_mime = _host_decode_base64(data.get("data"))
                    if raw is None:
                        return self._json({"error": "invalid base64"}, 400)
                    filename = _host_clean_filename(data.get("filename"))
                    mime = _host_mime(data.get("mime")) or data_mime
                filename = filename or (
                    "clipboard" + (mimetypes.guess_extension(mime or "") or ".bin")
                )
                e = _host_add("bin", raw, filename, mime)
                return self._json({"status": "ok", "id": e["id"]})

            if path in ("/clipboard", "/clipboard/image", "/1"):
                if multipart:
                    if multipart[0] == "files":
                        e = _host_add_bundle(multipart[1])
                    else:
                        e = _host_add("text", multipart[1])
                    return self._json({
                        "status": "ok",
                        "id": e["id"],
                        "type": e["type"],
                        "file_count": len(e.get("files", [])) or 1,
                    })

                if ctype == "application/json":
                    if filename:
                        e = _host_add("bin", body, filename, ctype)
                        return self._json({"status": "ok", "id": e["id"], "type": e["type"]})
                    try:
                        data = json.loads(body.decode("utf-8-sig"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        return self._json({"error": "invalid JSON"}, 400)
                    if isinstance(data, dict) and "data" in data:
                        raw, data_mime = _host_decode_base64(data.get("data"))
                        if raw is None:
                            return self._json({"error": "invalid base64"}, 400)
                        mime = _host_mime(data.get("mime")) or data_mime
                        name = _host_clean_filename(data.get("filename")) or (
                            "clipboard" + (mimetypes.guess_extension(mime or "") or ".bin")
                        )
                        e = _host_add("bin", raw, name, mime)
                        return self._json({"status": "ok", "id": e["id"], "type": e["type"]})
                    e = _host_add("text", _host_json_text(data))
                    return self._json({"status": "ok", "id": e["id"], "type": "text"})

                if ctype == "application/x-www-form-urlencoded":
                    form = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
                    key = next((k for k in ("text", "value", "content", "clipboard", "string") if k in form), None)
                    text = form[key][0] if key else (next(iter(form.values()))[0] if form else "")
                    e = _host_add("text", text)
                    return self._json({"status": "ok", "id": e["id"], "type": "text"})

                if filename is None and (
                    ctype.startswith("text/") or (not ctype and body and _host_looks_like_text(body, content_type))
                ):
                    text = _host_decode_text(body, content_type, allow_legacy=ctype.startswith("text/"))
                    if text is not None:
                        e = _host_add("text", text)
                        return self._json({"status": "ok", "id": e["id"], "type": "text"})

                if not body and filename is None and not ctype.startswith("text/"):
                    return self._json({"error": "no data"}, 400)
                filename = filename or (
                    "clipboard" + (mimetypes.guess_extension(ctype) or ".bin")
                )
                e = _host_add("bin", body, filename, ctype or None)
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
                    index = _host_load()
                    _host_save([])
                    for e in index:
                        _host_delete_files(e)
                return self._json({"status": "cleared"})
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[:2] == ["clipboard", "item"]:
                iid = parts[2]
                with _host_lock:
                    index = _host_load()
                    e = next((x for x in index if x["id"] == iid), None)
                    if e is None:
                        return self._json({"error": "not found"}, 404)
                    _host_save([x for x in index if x["id"] != iid])
                    _host_delete_files(e)
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
    with _local_history_lock:
        if os.path.exists(LOCAL_INDEX):
            try:
                with open(LOCAL_INDEX, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return []
        return []


def _local_save(index):
    with _local_history_lock:
        limit = config.get("max_local_history", 100)
        expired = index[limit:]
        temp = LOCAL_INDEX + ".tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(index[:limit], f, ensure_ascii=False, indent=2)
        os.replace(temp, LOCAL_INDEX)
        for old in expired:
            if old.get("file"):
                try:
                    os.remove(os.path.join(LOCAL_DIR, old["file"]))
                except OSError:
                    pass


def _now():
    import datetime
    return datetime.datetime.now().isoformat(timespec="seconds")


def record_local_text(text):
    with _local_history_lock:
        index = _local_load()
        if index and index[0].get("type") == "text" and index[0].get("text") == text:
            return
        index.insert(0, {"type": "text", "timestamp": _now(),
                         "preview": text[:140], "text": text})
        _local_save(index)


def record_local_image(img):
    with _local_history_lock:
        digest = _img_hash(img)
        index = _local_load()
        if index and index[0].get("type") == "image" and index[0].get("hash") == digest:
            return
        name = uuid.uuid4().hex[:12] + ".png"
        path = os.path.join(LOCAL_DIR, name)
        try:
            img.save(path)
            index.insert(0, {"type": "image", "timestamp": _now(),
                             "preview": f"image {img.width}x{img.height}", "file": name,
                             "hash": digest})
            _local_save(index)
        except Exception:
            if os.path.exists(path):
                os.remove(path)
            raise


def record_local_file(path):
    path = os.path.abspath(path)
    with _local_history_lock:
        index = _local_load()
        if (index and index[0].get("type") == "file"
                and _file_clipboard_key([index[0].get("path", "")]) == _file_clipboard_key([path])):
            return
        index.insert(0, {"type": "file", "timestamp": _now(),
                         "preview": os.path.basename(path), "path": path})
        _local_save(index)


def record_local_files(paths):
    paths = [os.path.abspath(path) for path in paths]
    if len(paths) == 1:
        record_local_file(paths[0])
        return
    with _local_history_lock:
        index = _local_load()
        if (index and index[0].get("type") == "bundle"
                and _file_clipboard_key(index[0].get("paths", [])) == _file_clipboard_key(paths)):
            return
        index.insert(0, {
            "type": "bundle",
            "timestamp": _now(),
            "preview": ", ".join(os.path.basename(path) for path in paths),
            "paths": paths,
            "file_count": len(paths),
        })
        _local_save(index)


# ---------------------------------------------------------------- actions
@_in_remote_operation
def action_send_clipboard(icon=None, item=None):
    try:
        files = get_clipboard_files()
        if files:
            push_files(files)
            record_local_files(files)
            notify(t("files_sent", n=len(files)) if len(files) > 1 else t("file_sent"))
            return
        img = get_clipboard_image()
        if img is not None:
            push_image(img)
            record_local_image(img)
            notify(t("image_sent"))
            return
        text = get_clipboard_text()
        if text:
            push_text(text)
            record_local_text(text)
            notify(t("text_sent"))
        else:
            notify(t("clip_empty"))
    except Exception as e:
        notify(t("send_err", e=e))


@_in_remote_operation
def _copy_remote_item(data, *, update_latest=True, suppress_notification=True):
    """Remember a receive only after Windows actually accepts the clipboard data."""
    kind = data.get("type")
    if kind == "text":
        value = data.get("text", "")
        set_clipboard_text(value)
        _set_local_upload_marker("text", value)
    elif kind == "image":
        try:
            image = Image.open(io.BytesIO(base64.b64decode(data["data"])))
            image.load()
        except (OSError, ValueError):
            # Preserve unsupported image formats (e.g. SVG/HEIC) as original files.
            data = dict(data, type="file")
            kind = "file"
            paths = save_remote_files(data)
            set_clipboard_files(paths)
            _set_local_upload_marker("files", _file_clipboard_key(paths))
        else:
            set_clipboard_image(image)
            restored = get_clipboard_image()
            _set_local_upload_marker("image", _img_hash(restored if restored is not None else image))
    elif kind in ("file", "bundle"):
        paths = save_remote_files(data)
        set_clipboard_files(paths)
        _set_local_upload_marker("files", _file_clipboard_key(paths))
    else:
        return False
    _remember_item(data.get("id"), file_seen=kind in ("file", "bundle"),
                   suppress_notification=suppress_notification, update_latest=update_latest)
    return kind


@_in_remote_operation
def action_get_latest(icon=None, item=None):
    try:
        with _remote_activity_lock:
            data = pull_latest()
            kind = data.get("type")
            kind = _copy_remote_item(data)
            if kind == "file" and data.get("type") == "image":
                data = dict(data, type="file")
        if kind == "text":
            notify_received("text", t("text_recv"))
        elif kind == "image":
            notify_received("image", t("image_recv"))
        elif kind == "file":
            paths = save_remote_files(data)
            record_local_files(paths)
            notify_received(
                "file",
                t("file_arrived", name=os.path.basename(paths[0])),
                action=lambda path=paths[0]: reveal_received_file(path),
            )
        elif kind == "bundle":
            paths = save_remote_files(data)
            record_local_files(paths)
            notify_received(
                "file",
                t("files_arrived", n=len(paths)),
                action=lambda: open_received_folder(),
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
            push_files(paths)
            record_local_files(paths)
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
    active_source = None
    next_connection_check = 0
    last_sequence = None
    while not stop_event.is_set():
        try:
            upload_failed = False
            source = _sync_source_key()
            if source != active_source:
                active_source = source
                last_server = _last_remembered_item()
                last_text = last_img = last_files = None
                last_sequence = None

            marker = _take_local_upload_marker()
            if marker:
                kind, value = marker
                if kind == "text":
                    last_text, last_img, last_files = value, None, None
                elif kind == "image":
                    last_img, last_text, last_files = value, None, None
                elif kind == "files":
                    last_files, last_text, last_img = value, None, None

            if time.monotonic() >= next_connection_check:
                check_connection()
                next_connection_check = time.monotonic() + 15

            sequence = _clipboard_sequence()
            files_changed = last_files and _file_clipboard_key([entry[0] for entry in last_files]) != last_files
            if ((config.get("monitor_clipboard") or config.get("auto_sync"))
                    and (sequence is None or sequence != last_sequence or files_changed)):
                files = get_clipboard_files()
                if files:
                    key = _file_clipboard_key(files)
                    if key != last_files:
                        record_local_files(files)
                        if config.get("auto_sync"):
                            try:
                                last_server = push_files(files) or last_server
                            except Exception:
                                upload_failed = True
                        if not upload_failed:
                            last_files, last_text, last_img = key, None, None
                else:
                    img = get_clipboard_image()
                    if img is not None:
                        h = _img_hash(img)
                        if h and h != last_img:
                            record_local_image(img)
                            if config.get("auto_sync"):
                                try:
                                    sent_id = push_image(img)
                                    if sent_id:
                                        last_server = sent_id
                                except Exception:
                                    upload_failed = True
                            if not upload_failed:
                                last_img, last_text, last_files = h, None, None
                    else:
                        text = get_clipboard_text()
                        if not text:
                            last_text = last_img = last_files = None
                        if text and text != last_text:
                            record_local_text(text)
                            if config.get("auto_sync"):
                                try:
                                    sent_id = push_text(text)
                                    if sent_id:
                                        last_server = sent_id
                                except Exception:
                                    upload_failed = True
                            if not upload_failed:
                                last_text, last_img, last_files = text, None, None
                if not upload_failed:
                    last_sequence = sequence

            if config.get("auto_receive_files", True) and not upload_failed:
                try:
                    received = _auto_receive_remote_files()
                    if received:
                        last_files = _file_clipboard_key(received)
                        last_text = last_img = None
                        last_server = _last_remembered_item()
                except Exception:
                    pass

            if config.get("auto_sync") and not upload_failed:
                try:
                    with _remote_operation():
                        data = poll_latest(last_server)
                        sid = data.get("id")
                        if sid and sid != last_server:
                            suppress = _consume_silent_item(sid)
                            if not suppress and data.get("type") == "text":
                                txt = data.get("text", "")
                                _copy_remote_item(data, suppress_notification=False)
                                last_text, last_img, last_files = txt, None, None
                                notify_received("text", t("text_arrived"))
                            elif not suppress and data.get("type") == "image":
                                copied_kind = _copy_remote_item(data, suppress_notification=False)
                                marker = _take_local_upload_marker()
                                if copied_kind == "image":
                                    last_img, last_text, last_files = marker[1], None, None
                                    notify_received("image", t("image_arrived"))
                                else:
                                    last_files, last_text, last_img = marker[1], None, None
                                    notify_received("file", t("file_arrived", name=data.get("filename", "image")),
                                                    action=lambda: open_received_folder())
                            elif not suppress and data.get("type") in ("file", "bundle"):
                                if config.get("auto_receive_files", True):
                                    _copy_remote_item(data)
                                    last_files = _file_clipboard_key(save_remote_files(data))
                                    last_text = last_img = None
                            last_server = sid
                            _remember_item(sid)
                except Exception:
                    pass
        except Exception:
            pass
        stop_event.wait(config.get("poll_interval", 3))


# ---------------------------------------------------------------- history window
_PALETTES = {
    "light": {
        "canvas": "#f4f6f8", "panel": "#ffffff", "field": "#ffffff", "soft": "#f2f4f7",
        "text": "#202830", "muted": "#627084", "border": "#d8dee5", "alternate": "#f8fafc",
        "selected": "#e8f1ff", "selected_text": "#1357b5", "hover": "#e8edf4",
        "scroll": "#bbc5d2", "scroll_active": "#8494a7", "disabled": "#99a2af",
        "primary": "#1668dc", "primary_hover": "#0d55b8", "support": "#9f315e",
        "connected_bg": "#ecfdf3", "connected_fg": "#15803d",
        "checking_bg": "#eff6ff", "checking_fg": "#2563eb",
        "auth_bg": "#fff7ed", "auth_fg": "#c2410c",
        "offline_bg": "#fef2f2", "offline_fg": "#b91c1c",
    },
    "dark": {
        "canvas": "#17191d", "panel": "#1e2126", "field": "#181b20", "soft": "#2b3038",
        "text": "#e4e8ef", "muted": "#a8b1bf", "border": "#3a414b", "alternate": "#24282f",
        "selected": "#253d60", "selected_text": "#b8d5ff", "hover": "#343d49",
        "scroll": "#667386", "scroll_active": "#9cacc0", "disabled": "#778190",
        "primary": "#1668dc", "primary_hover": "#0d55b8", "support": "#f5a5c4",
        "connected_bg": "#203b2c", "connected_fg": "#8be0aa",
        "checking_bg": "#26374f", "checking_fg": "#a7c8ff",
        "auth_bg": "#463321", "auth_fg": "#ffd096",
        "offline_bg": "#43272e", "offline_fg": "#ffa5b0",
    },
}


def _palette(widget=None):
    if widget is not None:
        colors = getattr(widget.winfo_toplevel(), "_colors", None)
        if colors is not None:
            return colors
    appearance = getattr(_root, "_appearance_override", None) or config.get("appearance", "dark")
    return _PALETTES.get(appearance, _PALETTES["dark"])


def _paint(widget, **roles):
    widget._color_roles = roles
    widget.configure(**{option: _palette(widget)[role] for option, role in roles.items()})
    return widget


def _modern_window(root, appearance=None):
    appearance = appearance or getattr(_root, "_appearance_override", None) or config.get("appearance", "dark")
    colors = _PALETTES.get(appearance, _PALETTES["dark"])
    root._colors = colors
    root.configure(background=colors["panel"])
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name, root=root).configure(family="Segoe UI", size=-13)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=("Segoe UI", -13), background=colors["panel"], foreground=colors["text"])
    style.configure("TFrame", background=colors["panel"])
    style.configure("TLabel", background=colors["panel"])
    style.configure("Muted.TLabel", foreground=colors["muted"])
    style.configure("Error.TLabel", foreground=colors["offline_fg"])
    style.configure("TButton", background=colors["soft"], bordercolor=colors["soft"],
                    lightcolor=colors["soft"], darkcolor=colors["soft"], padding=(10, 5), relief="flat", width=0)
    style.map("TButton", background=[("active", colors["hover"]), ("pressed", colors["selected"])],
              foreground=[("disabled", colors["disabled"]), ("!disabled", colors["text"])])
    for name in ("Primary.TButton", "Settings.Primary.TButton"):
        style.configure(name, background=colors["primary"], foreground="#ffffff", borderwidth=0,
                        bordercolor=colors["primary"], lightcolor=colors["primary"],
                        darkcolor=colors["primary"], padding=(12, 6))
        style.map(name, background=[("active", colors["primary_hover"])],
                  foreground=[("disabled", "#b9ccea"), ("!disabled", "#ffffff")])
    style.configure("TEntry", fieldbackground=colors["field"], bordercolor=colors["border"],
                    lightcolor=colors["field"], darkcolor=colors["field"], padding=5)
    style.configure("TCombobox", fieldbackground=colors["field"], background=colors["soft"],
                    bordercolor=colors["border"], lightcolor=colors["field"],
                    darkcolor=colors["field"], padding=4, arrowsize=12)
    style.map("TCombobox", fieldbackground=[("readonly", colors["field"])],
              selectbackground=[("readonly", colors["field"])],
              selectforeground=[("readonly", colors["text"])],
              foreground=[("readonly", colors["text"])])
    root.option_add("*TCombobox*Listbox.background", colors["field"])
    root.option_add("*TCombobox*Listbox.foreground", colors["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", colors["selected"])
    root.option_add("*TCombobox*Listbox.selectForeground", colors["text"])
    style.configure("TSpinbox", fieldbackground=colors["field"], bordercolor=colors["border"],
                    lightcolor=colors["field"], darkcolor=colors["field"], padding=4)
    for kind in ("Checkbutton", "Radiobutton"):
        style.configure("T" + kind, padding=(0, 5), background=colors["panel"])
        style.map("T" + kind, background=[("active", colors["panel"])],
                  foreground=[("disabled", colors["disabled"]), ("!disabled", colors["text"])])
        if "vista" in style.theme_names():
            indicator = f"Win.{kind}.indicator"
            if indicator not in style.element_names():
                style.element_create(indicator, "from", "vista", f"{kind}.indicator")
            style.layout("T" + kind, [(f"{kind}.padding", {"sticky": "nswe", "children": [
                (indicator, {"side": "left", "sticky": "w"}),
                (f"{kind}.focus", {"side": "left", "sticky": "w", "children": [
                    (f"{kind}.label", {"sticky": "nswe"}),
                ]}),
            ]})])
    style.configure("Treeview", rowheight=26, background=colors["panel"], fieldbackground=colors["panel"],
                    borderwidth=0, bordercolor=colors["panel"], lightcolor=colors["panel"],
                    darkcolor=colors["panel"], font=("Segoe UI", -13))
    style.configure("Treeview.Heading", background=colors["soft"], foreground=colors["muted"],
                    relief="flat", bordercolor=colors["soft"], lightcolor=colors["soft"],
                    darkcolor=colors["soft"], font=("Segoe UI", -12, "bold"), padding=(8, 4))
    style.map("Treeview", background=[("selected", colors["selected"])],
              foreground=[("selected", colors["selected_text"])])
    # Keep Tk's scrollbar bindings, but replace the embossed thumb with a flat image.
    thumb = f"Bridge.{appearance}.Vertical.Scrollbar.thumb"
    if thumb not in style.element_names():
        images = [ImageTk.PhotoImage(Image.new("RGB", (8, 24), colors[role]), master=_root)
                  for role in ("scroll", "scroll_active")]
        if not hasattr(_root, "_scroll_images"):
            _root._scroll_images = {}
        _root._scroll_images[appearance] = images
        style.element_create(thumb, "image", images[0], ("active", images[1]), border=2, sticky="nswe")
    style.layout("Slim.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {
        "sticky": "ns", "children": [(thumb, {"sticky": "nswe", "expand": 1})],
    })])
    style.configure("Slim.Vertical.TScrollbar", background=colors["scroll"], troughcolor=colors["panel"],
                    bordercolor=colors["panel"], lightcolor=colors["scroll"], darkcolor=colors["scroll"],
                    borderwidth=0, width=10, arrowsize=10, relief="flat")
    style.map("Slim.Vertical.TScrollbar", background=[("active", colors["scroll_active"])])
    for name in ("Segment.TRadiobutton", "Navigation.TRadiobutton"):
        style.layout(name, [("Radiobutton.padding", {"sticky": "nswe", "children": [
            ("Radiobutton.label", {"sticky": "nswe"}),
        ]})])
        style.configure(name, padding=(12, 7), anchor="w", background=colors["soft"], foreground=colors["muted"])
        style.map(name, background=[("selected", colors["selected"]), ("active", colors["hover"])],
                  foreground=[("selected", colors["selected_text"]), ("active", colors["text"])])
    style.configure("Icon.TButton", font=("Segoe MDL2 Assets", -18), padding=(8, 6),
                    width=2, borderwidth=0, background=colors["soft"])
    style.configure("Command.TButton", padding=(10, 6), borderwidth=0)
    style.configure("Support.TButton", background=colors["panel"], foreground=colors["support"], borderwidth=0)
    style.map("Support.TButton", background=[("active", colors["hover"])],
              foreground=[("!disabled", colors["support"])])
    style.layout("Preview.Toolbutton", [("Toolbutton.padding", {"sticky": "nswe", "children": [
        ("Toolbutton.label", {"sticky": "nswe"}),
    ]})])
    style.configure("Preview.Toolbutton", font=("Segoe MDL2 Assets", -18), padding=(8, 6),
                    width=2, borderwidth=0, background=colors["soft"])
    style.map("Preview.Toolbutton", background=[("selected", colors["selected"]), ("active", colors["hover"])],
              foreground=[("selected", colors["selected_text"]), ("!selected", colors["text"])])
    style.configure("Settings.Section.TLabelframe", padding=(0, 10), borderwidth=0, relief="flat",
                    bordercolor=colors["panel"], lightcolor=colors["panel"], darkcolor=colors["panel"],
                    background=colors["panel"])
    style.configure("Settings.Section.TLabelframe.Label", font=("Segoe UI", -13, "bold"))
    return style


def _update_appearance(appearance):
    def repaint(widget):
        roles = getattr(widget, "_color_roles", None)
        if roles:
            _paint(widget, **roles)
        if isinstance(widget, ttk.Treeview):
            widget.tag_configure("alternate", background=_palette(widget)["alternate"])
        if getattr(widget, "_glyph", None):
            _set_button_icon(widget)
        for child in widget.winfo_children():
            repaint(child)

    for window in _root.winfo_children():
        if getattr(window, "_view_name", None):
            _modern_window(window, appearance)
            repaint(window)


def _window_header(root, subtitle):
    header = _paint(tk.Frame(root, padx=16, pady=10), background="panel")
    header.pack(fill="x")
    try:
        with Image.open(ICON_PATH) as image:
            root._header_logo = ImageTk.PhotoImage(image.resize((24, 24), Image.Resampling.LANCZOS))
        _paint(tk.Label(header, image=root._header_logo), background="panel").pack(side="left")
    except OSError:
        pass
    title = _paint(tk.Frame(header), background="panel")
    title.pack(side="left", padx=(8, 0))
    _paint(tk.Label(title, text="Clipboard Bridge", font=("Segoe UI", -16, "bold")),
           background="panel", foreground="text").pack(side="left")
    _paint(tk.Label(title, text=subtitle, font=("Segoe UI", -12), padx=12),
           background="panel", foreground="muted").pack(side="left")
    return header


def _tooltip(widget, text):
    job = None
    popup = None

    def hide(_event=None):
        nonlocal job, popup
        if job is not None:
            widget.after_cancel(job)
            job = None
        if popup is not None:
            popup.destroy()
            popup = None

    def show():
        nonlocal job, popup
        job = None
        if not widget.winfo_exists():
            return
        popup = tk.Toplevel(widget)
        popup.overrideredirect(True)
        tk.Label(popup, text=widget.ui_label, background="#202830", foreground="#ffffff",
                 font=("Segoe UI", -12), padx=8, pady=5).pack()
        popup.update_idletasks()
        x = min(widget.winfo_rootx(), widget.winfo_screenwidth() - popup.winfo_reqwidth() - 8)
        y = widget.winfo_rooty() + widget.winfo_height() + 5
        popup.geometry(f"+{max(0, x)}+{y}")

    def schedule(_event=None):
        nonlocal job
        hide()
        job = widget.after(450, show)

    widget.bind("<Enter>", schedule, add="+")
    widget.bind("<Leave>", hide, add="+")
    widget.bind("<ButtonPress>", hide, add="+")
    widget.bind("<Destroy>", hide, add="+")
    widget.ui_label = text


def _set_button_icon(button):
    try:
        font = ImageFont.truetype(os.path.join(os.environ.get("WINDIR", "C:/Windows"),
                                             "Fonts", "segmdl2.ttf"), 16)
        images = []
        for role in (getattr(button, "_glyph_role", "text"), "disabled"):
            bitmap = Image.new("RGBA", (20, 20))
            ImageDraw.Draw(bitmap).text((10, 10), button._glyph, font=font,
                                        fill=_palette(button)[role], anchor="mm")
            images.append(ImageTk.PhotoImage(bitmap, master=button))
        button._glyph_images = images
        button.configure(image=(images[0], "disabled", images[1]))
    except OSError:
        pass


def _command_button(parent, name, label, glyph, command):
    button = ttk.Button(parent, name=name, text=label, compound="left", style="Command.TButton", command=command)
    button._glyph = glyph
    _set_button_icon(button)
    _tooltip(button, label)
    return button


def _existing_view(name):
    for window in _root.winfo_children():
        if getattr(window, "_view_name", None) == name:
            window.deiconify()
            window.lift()
            window.focus_set()
            return window
    return None


class _SettingsNavigation(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._pages = []
        self._selection = tk.StringVar(master=self)
        self._rail = ttk.Frame(self, width=150)
        self._rail.pack(side="left", fill="y", padx=(0, 12))
        self._rail.pack_propagate(False)
        self._content = ttk.Frame(self)
        self._content.pack(side="left", fill="both", expand=True)
        donation = ttk.Frame(self._rail)
        donation.pack(side="bottom", fill="x", pady=10)
        self._support_note = ttk.Label(donation, name="support_note", text=t("support_note"),
                                       style="Muted.TLabel", font=("Segoe UI", -11),
                                       wraplength=138, justify="left")
        self._support_note.pack(fill="x", padx=6, pady=(0, 8))
        support = _command_button(donation, "support", "Ko-fi", "\ueb51",
                                  lambda: _run_bg(lambda: webbrowser.open("https://ko-fi.com/mattboxx")))
        support._glyph_role = "support"
        support.configure(style="Support.TButton")
        _set_button_icon(support)
        support.ui_label = t("support")
        support.pack(anchor="w")
        self._support_button = support

    def support_language(self, language):
        self._support_note.configure(text=STRINGS[language]["support_note"])
        self._support_button.ui_label = STRINGS[language]["support"]

    def add(self, page, *, text):
        self._pages.append(page)
        ttk.Radiobutton(self._rail, text=text, value=str(page), variable=self._selection,
                        style="Navigation.TRadiobutton", command=lambda: self.select(page)).pack(
                            fill="x", pady=(0, 4))
        if len(self._pages) == 1:
            self.select(page)

    def tabs(self):
        return tuple(str(page) for page in self._pages)

    def select(self, target=None):
        if target is None:
            return self._selection.get()
        if isinstance(target, int):
            target = self._pages[target]
        for page in self._pages:
            page.pack_forget()
        page = next(page for page in self._pages if str(page) == str(target))
        page.pack(in_=self._content, fill="both", expand=True)
        self._selection.set(str(page))


def _settings_page(notebook):
    page = ttk.Frame(notebook)
    canvas = _paint(tk.Canvas(page, highlightthickness=0, borderwidth=0), background="panel")
    scrollbar = ttk.Scrollbar(page, orient="vertical", command=canvas.yview, style="Slim.Vertical.TScrollbar")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    content = ttk.Frame(canvas, padding=(20, 12))
    window = canvas.create_window((0, 0), window=content, anchor="nw")
    content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))

    def scroll(event):
        canvas.yview_scroll(-int(event.delta / 120), "units")
        return "break"

    def bind_scroll(parent):
        if not isinstance(parent, (ttk.Entry, ttk.Combobox, ttk.Spinbox)):
            parent.bind("<MouseWheel>", scroll, add="+")
        for child in parent.winfo_children():
            bind_scroll(child)

    scroll_job = page.after_idle(lambda: bind_scroll(content))
    page.bind("<Destroy>", lambda event: page.after_cancel(scroll_job) if event.widget == page else None)
    canvas.bind("<MouseWheel>", scroll)
    return page, content


def _history_table(parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, padx=16)
    tree = ttk.Treeview(frame, columns=("content", "type", "date", "size"),
                        show="headings", selectmode="browse")
    for name, width, minimum, stretch, anchor in (
        ("content", 500, 230, True, "w"), ("type", 95, 95, False, "w"),
        ("date", 125, 125, False, "w"), ("size", 65, 65, False, "e"),
    ):
        tree.heading(name, text=t("column_" + name), anchor=anchor)
        tree.column(name, width=width, minwidth=minimum, stretch=stretch, anchor=anchor)
    tree.tag_configure("alternate", background=_palette(parent)["alternate"])
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview, style="Slim.Vertical.TScrollbar")
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return tree


def _fill_history_table(tree, items):
    tree.delete(*tree.get_children())
    kinds = {"text": "text_type", "image": "image_type", "file": "file_type", "bundle": "bundle_type"}
    for index, item in enumerate(items):
        size = item.get("size")
        if size is None:
            size_text = ""
        elif size < 1024:
            size_text = f"{size} B"
        else:
            size_text = f"{size / (1024 ** (2 if size >= 1024 ** 2 else 1)):.1f} {'MB' if size >= 1024 ** 2 else 'KB'}"
        date = str(item.get("timestamp") or "").replace("T", " ")[:16]
        tree.insert("", "end", iid=str(index), values=(
            (item.get("preview") or item.get("filename") or "").replace("\n", " ").replace("\r", " "),
            t(kinds.get(item.get("type"), "file_type")), date, size_text,
        ), tags=("alternate",) if index % 2 else ())


def _copy_local_item(item):
    kind = item.get("type")
    if kind == "text":
        set_clipboard_text(item.get("text", ""))
    elif kind == "image" and item.get("file"):
        with Image.open(os.path.join(LOCAL_DIR, item["file"])) as image:
            set_clipboard_image(image)
    elif kind in ("file", "bundle"):
        paths = item.get("paths", []) if kind == "bundle" else [item.get("path")]
        if not paths or not all(path and os.path.isfile(path) for path in paths):
            raise FileNotFoundError(t("unavailable"))
        set_clipboard_files(paths)
    else:
        raise ValueError(t("unavailable"))


def open_history_window(icon=None, item=None):
    if _existing_view("history") is not None:
        return
    root = tk.Toplevel(_root)
    root._view_name = "history"
    root.title(t("win_history"))
    root.geometry("980x660")
    root.minsize(760, 480)
    _modern_window(root)
    apply_window_icon(root)
    header = _window_header(root, t("history").rstrip("\u2026"))
    _command_button(header, "settings", t("settings").rstrip("\u2026"), "\ue713", open_settings).pack(side="right", padx=(8, 0))
    receive = ttk.Button(header, text=t("receive_short"), style="Primary.TButton",
                         command=lambda: _run_bg(action_get_latest))
    receive.pack(side="right")
    _tooltip(receive, t("receive_now"))
    send = ttk.Button(header, text=t("send_short"), command=lambda: _run_bg(action_send_clipboard))
    send.pack(side="right", padx=(0, 6))
    _tooltip(send, t("send_now"))

    ui_q = queue.Queue()
    search_job = pump_job = None
    request_generation = 0
    offset = 0
    page_size = 100
    items = []
    loaded_source = None
    source = tk.StringVar(master=root, value="server")
    query = tk.StringVar(master=root)
    preview_visible = tk.BooleanVar(master=root, value=False)
    status = tk.StringVar(master=root)
    toolbar = ttk.Frame(root)
    toolbar.pack(fill="x", padx=16, pady=(2, 12))
    sources = ttk.Frame(toolbar)
    sources.pack(side="left", padx=(0, 12))
    for value, key in (("server", "tab_server"), ("local", "tab_local")):
        ttk.Radiobutton(sources, text=t(key), value=value, variable=source,
                        style="Segment.TRadiobutton", command=lambda: refresh(reset=True)).pack(side="left")
    refresh_button = _command_button(toolbar, "refresh", t("refresh"), "\ue72c", lambda: refresh())
    refresh_button.pack(side="right", padx=(6, 0))
    kinds = ("", "text", "image", "file", "bundle")
    kind_selector = ttk.Combobox(toolbar, state="readonly", width=13,
        values=[t(key) for key in ("all_types", "text_type", "image_type", "file_type", "bundle_type")])
    kind_selector.current(0)
    kind_selector.pack(side="right", padx=(8, 0))
    search_symbol = ttk.Label(toolbar, text="\ue721", font=("Segoe MDL2 Assets", -14))
    search_symbol.pack(side="left", padx=(0, 6))
    _tooltip(search_symbol, t("search_history"))
    search_entry = ttk.Entry(toolbar, textvariable=query)
    search_entry.pack(side="left", fill="x", expand=True)
    _tooltip(search_entry, t("history_search"))

    footer = ttk.Frame(root, padding=(16, 10))
    footer.pack(side="bottom", fill="x")
    preview_bar = ttk.Frame(root, padding=(16, 8))
    ttk.Label(preview_bar, text=t("preview"), style="Muted.TLabel").pack(anchor="w")
    preview_text = _paint(tk.Text(preview_bar, height=3, wrap="word", state="disabled",
                           font=("Segoe UI", -13), borderwidth=0,
                           highlightthickness=0, padx=8, pady=6), background="soft", foreground="text",
                           selectbackground="selected", selectforeground="text", insertbackground="text")
    preview_scroll = ttk.Scrollbar(preview_bar, orient="vertical", command=preview_text.yview,
                                   style="Slim.Vertical.TScrollbar")
    preview_text.configure(yscrollcommand=preview_scroll.set)
    preview_text.pack(side="left", fill="x", expand=True)
    preview_scroll.pack(side="right", fill="y")
    listing = _history_table(root)
    empty = ttk.Label(listing.master, text=t("no_results"), style="Muted.TLabel")

    def selected():
        selection = listing.selection()
        return items[int(selection[0])] if selection and int(selection[0]) < len(items) else None

    def update_selection(*_args):
        entry = selected()
        copy_button.configure(state="normal" if entry else "disabled")
        delete_button.configure(state="normal" if entry else "disabled")
        local_send.configure(state="normal" if entry else "disabled")
        value = t("preview_empty")
        if entry:
            members = entry.get("files", [])
            value = "\n".join(member.get("filename", "") for member in members) if members else (
                entry.get("text") or entry.get("preview") or entry.get("filename") or "")
        preview_text.configure(state="normal")
        preview_text.delete("1.0", "end")
        preview_text.insert("1.0", value[:4000])
        preview_text.configure(state="disabled")

    def show_preview():
        if preview_visible.get():
            preview_bar.pack(side="bottom", fill="x", before=listing.master)
        else:
            preview_bar.pack_forget()

    def fill(page):
        items[:] = page.get("items", [])
        _fill_history_table(listing, items)
        if items:
            listing.selection_set("0")
            listing.focus("0")
            empty.place_forget()
        else:
            empty.place(relx=.5, rely=.5, anchor="center")
        status.set(t("history_results", shown=len(items), total=page.get("total", len(items))))
        previous_button.configure(state="normal" if offset else "disabled")
        next_button.configure(state="normal" if page.get("has_more") else "disabled")
        update_selection()

    def refresh(reset=False):
        nonlocal request_generation, offset, loaded_source
        if reset:
            offset = 0
        request_generation += 1
        generation = request_generation
        search, kind = query.get(), kinds[max(0, kind_selector.current())]
        is_server = source.get() == "server"
        for button in (previous_button, next_button):
            button.configure(state="disabled")
        if is_server:
            local_send.pack_forget()
            delete_button.pack(side="left", after=copy_button, padx=4)
            page_controls.pack(side="right", before=copy_button)
        else:
            delete_button.pack_forget()
            local_send.pack(side="left", after=copy_button, padx=6)
            page_controls.pack_forget()
            loaded_source = None
            fill({"items": _filter_history(_local_load(), search, kind)})
            return
        source_key, requested_offset = _sync_source_key(), offset
        items.clear()
        listing.delete(*listing.get_children())
        empty.place_forget()
        update_selection()
        status.set(t("loading"))

        def deliver(page=None):
            nonlocal loaded_source
            if generation != request_generation or not root.winfo_exists():
                return
            if source_key != _sync_source_key():
                refresh(reset=True)
            elif page is None:
                status.set(t("history_error"))
            else:
                loaded_source = source_key
                fill(page)

        def work():
            try:
                with _remote_activity_lock:
                    if generation != request_generation:
                        return
                    page = fetch_history_page(page_size, search, kind, requested_offset)
                ui_q.put(lambda: deliver(page))
            except Exception:
                ui_q.put(deliver)
        threading.Thread(target=work, daemon=True).start()

    def copy_item(*_args):
        entry = selected()
        if entry is None:
            return
        is_server, source_key = source.get() == "server", loaded_source

        def work():
            try:
                if not is_server:
                    _copy_local_item(entry)
                    notify(t("copied"))
                    return
                with _remote_operation():
                    if source_key != _sync_source_key():
                        ui_q.put(lambda: refresh(reset=True))
                        return
                    full = fetch_item(entry["id"])
                    kind = _copy_remote_item(full, update_latest=False)
                    if kind in ("file", "bundle"):
                        full = dict(full, type=kind)
                        paths = save_remote_files(full)
                        record_local_files(paths)
                        notify_received("file", t("files_arrived", n=len(paths)) if len(paths) > 1
                                        else t("file_arrived", name=os.path.basename(paths[0])),
                                        action=(lambda: open_received_folder()) if len(paths) > 1
                                        else (lambda path=paths[0]: reveal_received_file(path)))
                    elif kind:
                        notify(t("copied"))
            except Exception as error:
                notify(t("recv_err", e=error))
        _run_bg(work)
        return "break"

    def send_local():
        entry = selected()
        if entry is None or source.get() != "local":
            return

        def work():
            try:
                if entry["type"] == "text":
                    push_text(entry.get("text", ""))
                elif entry["type"] == "image" and entry.get("file"):
                    with Image.open(os.path.join(LOCAL_DIR, entry["file"])) as image:
                        push_image(image)
                elif entry["type"] in ("file", "bundle"):
                    paths = entry.get("paths", []) if entry["type"] == "bundle" else [entry.get("path")]
                    push_files(paths)
                else:
                    raise ValueError(t("unavailable"))
                notify(t("sent_server"))
            except Exception as error:
                notify(t("send_err", e=error))
        _run_bg(work)

    def delete_item(*_args):
        entry = selected()
        if entry is None or source.get() != "server":
            return
        if not messagebox.askyesno(t("delete"), t("confirm_delete"), parent=root):
            return
        source_key = loaded_source

        def work():
            try:
                with _remote_operation():
                    if source_key != _sync_source_key():
                        ui_q.put(lambda: refresh(reset=True))
                        return
                    response = requests.delete(f"{server_url()}/clipboard/item/{entry['id']}",
                                               headers=auth_headers(), params=auth_params(), timeout=5)
                    response.raise_for_status()
                ui_q.put(lambda: refresh())
            except Exception as error:
                notify(t("recv_err", e=error))
        _run_bg(work)

    copy_button = ttk.Button(footer, text=t("copy_selected"), style="Primary.TButton", command=copy_item)
    copy_button.pack(side="left")
    delete_button = _command_button(footer, "delete", t("delete"), "\ue74d", delete_item)
    local_send = ttk.Button(footer, text=t("send_to_server"), command=send_local)
    preview_button = ttk.Checkbutton(footer, name="preview", text=t("show_preview"),
                                    variable=preview_visible, command=show_preview)
    preview_button.pack(side="left", padx=(4, 0))
    _tooltip(preview_button, t("show_preview"))
    page_controls = ttk.Frame(footer)

    def move_page(direction):
        nonlocal offset
        offset = max(0, offset + direction * page_size)
        refresh()

    previous_button = _command_button(page_controls, "previous", t("previous"), "\ue72b", lambda: move_page(-1))
    previous_button.pack(side="left")
    next_button = _command_button(page_controls, "next", t("next"), "\ue72a", lambda: move_page(1))
    next_button.pack(side="left", padx=(4, 0))
    status_label = ttk.Label(footer, textvariable=status, style="Muted.TLabel", wraplength=340)
    status_label.pack(side="left", fill="x", expand=True, padx=12)
    status_label.bind("<Configure>", lambda event: status_label.configure(wraplength=max(80, event.width)))

    menu = tk.Menu(root, tearoff=False)

    def context_menu(event):
        row = listing.identify_row(event.y)
        if not row:
            return
        listing.selection_set(row)
        menu.delete(0, "end")
        menu.add_command(label=t("copy_selected"), command=copy_item)
        menu.add_command(label=t("preview"), command=lambda: (preview_visible.set(True), show_preview()))
        if source.get() == "server":
            menu.add_command(label=t("delete"), command=delete_item)
        else:
            menu.add_command(label=t("send_to_server"), command=send_local)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def double_click(event):
        row = listing.identify_row(event.y)
        if row:
            listing.selection_set(row)
            copy_item()
        return "break"

    listing.bind("<<TreeviewSelect>>", update_selection)
    listing.bind("<Double-1>", double_click)
    listing.bind("<Return>", copy_item)
    listing.bind("<Delete>", delete_item)
    listing.bind("<Button-3>", context_menu)

    def apply_search(*_args):
        nonlocal search_job
        if search_job is not None:
            root.after_cancel(search_job)
        search_job = None
        refresh(reset=True)

    def schedule_search(*_args):
        nonlocal search_job
        if search_job is not None:
            root.after_cancel(search_job)
        search_job = root.after(250, apply_search)

    query.trace_add("write", schedule_search)
    kind_selector.bind("<<ComboboxSelected>>", apply_search)
    search_entry.bind("<Return>", apply_search)
    def focus_search(_event):
        search_entry.focus_set()
        search_entry.selection_range(0, "end")
        return "break"

    root.bind("<Control-f>", focus_search)

    def pump():
        nonlocal pump_job
        try:
            while True:
                ui_q.get_nowait()()
        except queue.Empty:
            pass
        if root.winfo_exists():
            pump_job = root.after(80, pump)

    def close_history():
        nonlocal request_generation
        request_generation += 1
        for job in (search_job, pump_job):
            if job is not None:
                root.after_cancel(job)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close_history)
    root.after(0, refresh)
    pump_job = root.after(80, pump)


# ---------------------------------------------------------------- settings window
def open_settings(icon=None, item=None):
    if _existing_view("settings") is not None:
        return
    root = tk.Toplevel(_root)
    root._view_name = "settings"
    root.title(t("win_settings"))
    root.geometry("760x620")
    root.minsize(700, 520)
    style = _modern_window(root)
    root.attributes("-topmost", True)
    apply_window_icon(root)

    def release_topmost():
        try:
            root.attributes("-topmost", False)
        except tk.TclError:
            pass

    release_job = root.after(300, release_topmost)

    style.configure("Settings.TCheckbutton", padding=(0, 5))

    _window_header(root, f"{t('settings').rstrip('…')} · {t('version_label', version=APP_VERSION)}")

    body = ttk.Frame(root, padding=(12, 8, 12, 0))
    body.pack(fill="both", expand=True)
    notebook = _SettingsNavigation(body)
    notebook.pack(fill="both", expand=True)

    general_page, general_tab = _settings_page(notebook)
    connection_page, connection_tab = _settings_page(notebook)
    automation_page, automation_tab = _settings_page(notebook)
    shortcuts_page, shortcuts_tab = _settings_page(notebook)
    notebook.add(general_page, text=t("tab_general"))
    notebook.add(connection_page, text=t("tab_connection"))
    notebook.add(automation_page, text=t("tab_automation"))
    notebook.add(shortcuts_page, text=t("tab_shortcuts"))

    entries = {}

    def add_field(parent, row, label, key, secret=False):
        parent.grid_columnconfigure(1, weight=1)
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=6)
        variable = tk.StringVar(value=str(config.get(key, "")))
        entry = ttk.Entry(parent, textvariable=variable, show="*" if secret else "")
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        entries[key] = variable

    mode = tk.StringVar(value=config.get("mode", "client"))
    mode_box = ttk.LabelFrame(
        general_tab,
        text=t("section_mode"),
        style="Settings.Section.TLabelframe",
    )
    mode_box.pack(fill="x", pady=(0, 12))
    ttk.Radiobutton(
        mode_box,
        text=t("mode_client"),
        value="client",
        variable=mode,
    ).pack(anchor="w", pady=(0, 8))
    ttk.Radiobutton(
        mode_box,
        text=t("mode_server"),
        value="server",
        variable=mode,
    ).pack(anchor="w")

    application_box = ttk.LabelFrame(
        general_tab,
        text=t("section_application"),
        style="Settings.Section.TLabelframe",
    )
    application_box.pack(fill="x")
    application_box.grid_columnconfigure(1, weight=1)
    ttk.Label(application_box, text=t("lbl_language")).grid(
        row=0, column=0, sticky="w", padx=(0, 14), pady=6
    )
    language = tk.StringVar(
        value="Italiano" if config.get("lang", "en") == "it" else "English"
    )
    root._language_var = language
    language.trace_add("write", lambda *_args: notebook.support_language(
        "it" if language.get() == "Italiano" else "en"))
    ttk.Combobox(
        application_box,
        textvariable=language,
        values=("English", "Italiano"),
        state="readonly",
    ).grid(row=0, column=1, sticky="ew", pady=6)
    ttk.Label(application_box, text=t("lbl_history_limit")).grid(
        row=1, column=0, sticky="w", padx=(0, 14), pady=6
    )
    history_limit = tk.StringVar(value=str(config.get("max_local_history", 100)))
    ttk.Spinbox(
        application_box,
        textvariable=history_limit,
        from_=10,
        to=1000,
        increment=10,
    ).grid(row=1, column=1, sticky="ew", pady=6)

    appearance = tk.StringVar(master=root, value=config.get("appearance", "dark"))

    def preview_appearance():
        _root._appearance_override = appearance.get()
        _update_appearance(appearance.get())

    ttk.Label(application_box, text=t("lbl_appearance")).grid(
        row=2, column=0, sticky="w", padx=(0, 14), pady=6)
    appearance_controls = ttk.Frame(application_box)
    appearance_controls.grid(row=2, column=1, sticky="w", pady=6)
    for value, key in (("light", "light_theme"), ("dark", "dark_theme")):
        ttk.Radiobutton(appearance_controls, text=t(key), value=value, variable=appearance,
                        command=preview_appearance, style="Segment.TRadiobutton").pack(side="left")

    status_box = ttk.LabelFrame(
        connection_tab,
        text=t("section_status"),
        style="Settings.Section.TLabelframe",
    )
    status_box.pack(fill="x", pady=(0, 12))
    status_panel = _paint(tk.Frame(status_box, padx=12, pady=10), background="checking_bg")
    status_panel.pack(fill="x")
    status_dot = _paint(tk.Label(
        status_panel,
        text="●",
        font=("Segoe UI", -13),
    ), background="checking_bg", foreground="checking_fg")
    status_dot.grid(row=0, column=0, sticky="w", padx=(0, 8))
    status_label = _paint(tk.Label(
        status_panel,
        text=settings_connection_status_text(),
        font=("Segoe UI", -13, "bold"),
        anchor="w",
        justify="left",
        wraplength=300,
    ), background="checking_bg", foreground="checking_fg")
    status_label.grid(row=0, column=1, sticky="ew")
    status_panel.grid_columnconfigure(1, weight=1)

    server_box = ttk.LabelFrame(
        connection_tab,
        text=t("section_server"),
        style="Settings.Section.TLabelframe",
    )
    server_box.pack(fill="x", pady=(0, 12))
    add_field(server_box, 0, t("lbl_ip"), "server_ip")
    add_field(server_box, 1, t("lbl_port"), "server_port")
    add_field(server_box, 2, t("lbl_host_port"), "host_port")

    account_box = ttk.LabelFrame(
        connection_tab,
        text=t("section_account"),
        style="Settings.Section.TLabelframe",
    )
    account_box.pack(fill="x")
    add_field(account_box, 0, t("lbl_token"), "token", secret=True)
    add_field(account_box, 1, t("lbl_user"), "username")
    add_field(account_box, 2, t("lbl_pass"), "password", secret=True)

    auto = tk.BooleanVar(value=config.get("auto_sync", False))
    auto_files = tk.BooleanVar(value=config.get("auto_receive_files", True))
    mon = tk.BooleanVar(value=config.get("monitor_clipboard", True))
    notifications = tk.BooleanVar(value=config.get("notifications_enabled", True))
    notify_text = tk.BooleanVar(value=config.get("notify_text", True))
    notify_images = tk.BooleanVar(value=config.get("notify_images", True))
    notify_files = tk.BooleanVar(value=config.get("notify_files", True))
    automation_box = ttk.LabelFrame(
        automation_tab,
        text=t("tab_automation"),
        style="Settings.Section.TLabelframe",
    )
    automation_box.pack(fill="x")
    ttk.Checkbutton(
        automation_box,
        text=t("chk_autosync"),
        variable=auto,
        style="Settings.TCheckbutton",
    ).pack(anchor="w")
    ttk.Checkbutton(
        automation_box,
        text=t("chk_auto_files"),
        variable=auto_files,
        style="Settings.TCheckbutton",
    ).pack(anchor="w")
    ttk.Checkbutton(
        automation_box,
        text=t("chk_monitor"),
        variable=mon,
        style="Settings.TCheckbutton",
    ).pack(anchor="w")
    interval_box = ttk.Frame(automation_box)
    interval_box.pack(fill="x", pady=(10, 0))
    add_field(interval_box, 0, t("lbl_interval"), "poll_interval")

    notifications_box = ttk.LabelFrame(
        automation_tab,
        text=t("section_notifications"),
        style="Settings.Section.TLabelframe",
    )
    notifications_box.pack(fill="x", pady=(12, 0))
    notification_category_controls = []

    def update_notification_controls():
        state = "normal" if notifications.get() else "disabled"
        for control in notification_category_controls:
            control.config(state=state)

    ttk.Checkbutton(
        notifications_box,
        text=t("chk_notifications"),
        variable=notifications,
        command=update_notification_controls,
        style="Settings.TCheckbutton",
    ).pack(anchor="w")
    for label, variable in (
        (t("chk_notify_text"), notify_text),
        (t("chk_notify_images"), notify_images),
        (t("chk_notify_files"), notify_files),
    ):
        control = ttk.Checkbutton(
            notifications_box,
            text=label,
            variable=variable,
            style="Settings.TCheckbutton",
        )
        control.pack(anchor="w", padx=(22, 0))
        notification_category_controls.append(control)
    update_notification_controls()

    hk = tk.BooleanVar(value=config.get("hotkeys_enabled", True))
    shortcuts_box = ttk.LabelFrame(
        shortcuts_tab,
        text=t("tab_shortcuts"),
        style="Settings.Section.TLabelframe",
    )
    shortcuts_box.pack(fill="x")
    ttk.Checkbutton(
        shortcuts_box,
        text=t("chk_hotkeys"),
        variable=hk,
        style="Settings.TCheckbutton",
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
    add_field(shortcuts_box, 1, t("lbl_hk_send"), "hotkey_send")
    add_field(shortcuts_box, 2, t("lbl_hk_recv"), "hotkey_receive")

    footer = ttk.Frame(root, padding=(18, 12, 18, 16))
    footer.pack(side="bottom", fill="x", before=body)
    msg = ttk.Label(footer, text="", style="Error.TLabel", wraplength=290)
    msg.pack(side="left", fill="x", expand=True)

    def pending_connection_values(validate_interval=True):
        try:
            port = int(entries["server_port"].get())
            host_port = int(entries["host_port"].get())
        except ValueError:
            msg.config(text=t("err_numbers"))
            notebook.select(connection_page)
            return None
        if not (1 <= port <= 65535 and 1 <= host_port <= 65535):
            msg.config(text=t("err_ports"))
            notebook.select(connection_page)
            return None
        if validate_interval:
            try:
                interval = int(entries["poll_interval"].get())
            except ValueError:
                msg.config(text=t("err_numbers"))
                notebook.select(automation_page)
                return None
            try:
                max_history = int(history_limit.get())
            except ValueError:
                msg.config(text=t("err_numbers"))
                notebook.select(general_page)
                return None
        else:
            interval = config.get("poll_interval", 3)
            max_history = config.get("max_local_history", 100)
        values = dict(config)
        values.update({
            "lang": "it" if language.get() == "Italiano" else "en",
            "appearance": appearance.get(),
            "mode": mode.get() if mode.get() in ("client", "server") else "client",
            "server_ip": entries["server_ip"].get().strip(),
            "server_port": port,
            "host_port": host_port,
            "token": entries["token"].get().strip(),
            "username": entries["username"].get().strip(),
            "password": entries["password"].get(),
            "poll_interval": interval if interval > 0 else 3,
            "max_local_history": min(1000, max(10, max_history)),
        })
        return values

    def show_connection_status():
        try:
            exists = root.winfo_exists()
        except tk.TclError:
            return
        if not exists:
            return
        state = _connection_state if _connection_state in ("connected", "checking", "auth", "offline") else "checking"
        _paint(status_panel, background=state + "_bg")
        _paint(status_dot, background=state + "_bg", foreground=state + "_fg")
        _paint(status_label, background=state + "_bg", foreground=state + "_fg")
        status_label.config(text=settings_connection_status_text())
        connection_button.config(state="normal")

    def test_connection():
        values = pending_connection_values(validate_interval=False)
        if values is None:
            connection_button.config(state="normal")
            return
        msg.config(text="")
        connection_button.config(state="disabled")
        _set_connection_state("checking")
        show_connection_status()

        def work():
            check_connection(values)
            _cmd_q.put(show_connection_status)
        threading.Thread(target=work, daemon=True).start()

    connection_button = ttk.Button(
        status_panel,
        text=t("check_connection"),
        command=test_connection,
    )
    connection_button.grid(row=0, column=2, sticky="e", padx=(12, 0))

    def save():
        values = pending_connection_values()
        if values is None:
            return
        host_port = values["host_port"]
        old_mode = config.get("mode", "client")
        old_host_port = config.get("host_port", 5088)
        config.update(values)
        _root._appearance_override = None
        _update_appearance(config["appearance"])
        config["hotkey_send"] = entries["hotkey_send"].get().strip().lower() or "ctrl+alt+c"
        config["hotkey_receive"] = entries["hotkey_receive"].get().strip().lower() or "ctrl+alt+v"
        config["auto_sync"] = auto.get()
        config["auto_receive_files"] = auto_files.get()
        config["monitor_clipboard"] = mon.get()
        config["notifications_enabled"] = notifications.get()
        config["notify_text"] = notify_text.get()
        config["notify_images"] = notify_images.get()
        config["notify_files"] = notify_files.get()
        config["hotkeys_enabled"] = hk.get()
        save_config(config)
        with _local_history_lock:
            _local_save(_local_load())
        if config["hotkeys_enabled"]:
            register_hotkeys()
        else:
            unregister_hotkeys()
        if config.get("mode") == "server":
            if old_mode != "server" or host_port != old_host_port:
                stop_host_server()
                if start_host_server():
                    notify(t("server_on", addr=server_address()))
        elif old_mode == "server":
            stop_host_server()
            notify(t("client_on"))
        _set_connection_state("checking")
        active_icon = icon or _icon
        if active_icon is not None:
            try:
                active_icon.update_menu()
            except Exception:
                pass
        close_settings()
        notify(t("settings_saved"))
        _run_bg(check_connection)

    def close_settings():
        for job in (release_job, connection_job):
            root.after_cancel(job)
        _root._appearance_override = None
        _update_appearance(config.get("appearance", "dark"))
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close_settings)
    actions = ttk.Frame(footer)
    actions.pack(side="right")
    ttk.Button(actions, text=t("cancel"), command=close_settings).pack(side="left", padx=(0, 8))
    ttk.Button(
        actions,
        text=t("save"),
        command=save,
        style="Settings.Primary.TButton",
    ).pack(side="left")
    connection_job = root.after(120, test_connection)


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


# ---------------------------------------------------------------- menu actions
def _set_lang(code):
    def handler(icon, item):
        config["lang"] = code
        save_config(config)
        icon.update_menu()
        def update_support_language():
            for window in _root.winfo_children():
                if getattr(window, "_view_name", None) == "settings":
                    window._language_var.set("Italiano" if code == "it" else "English")
        if _root is not None:
            _cmd_q.put(update_support_language)
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
        MenuItem(lambda i: tray_connection_text(), lambda icon, item: None, enabled=False),
        Menu.SEPARATOR,
        MenuItem(lambda i: t("send"), lambda icon, item: _run_bg(action_send_clipboard)),
        MenuItem(lambda i: t("recv"), lambda icon, item: _run_bg(action_get_latest)),
        Menu.SEPARATOR,
        MenuItem(lambda i: t("send_file"), lambda icon, item: _cmd_q.put(action_send_file)),
        MenuItem(lambda i: t("open_recv"), open_received_folder),
        Menu.SEPARATOR,
        MenuItem(lambda i: t("history"), lambda icon, item: _cmd_q.put(open_history_window), default=True),
        MenuItem(lambda i: t("language"), Menu(
            MenuItem("English", _set_lang("en"),
                     checked=lambda i: config.get("lang", "en") == "en", radio=True),
            MenuItem("Italiano", _set_lang("it"),
                     checked=lambda i: config.get("lang", "en") == "it", radio=True),
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


def _acquire_single_instance(name="Local\\ClipboardBridge.Client.SingleInstance"):
    """Return False when another Clipboard Bridge process is already running."""
    global _instance_mutex
    if os.name != "nt":
        return True

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_mutex = kernel32.CreateMutexW
    create_mutex.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    create_mutex.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    mutex = create_mutex(None, False, name)
    if not mutex:
        return True
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        close_handle(mutex)
        return False
    _instance_mutex = mutex
    return True


def _release_single_instance():
    global _instance_mutex
    if os.name == "nt" and _instance_mutex:
        try:
            close_handle = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
            close_handle.argtypes = (wintypes.HANDLE,)
            close_handle.restype = wintypes.BOOL
            close_handle(_instance_mutex)
        except Exception:
            pass
    _instance_mutex = None


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
    if not _acquire_single_instance():
        return
    try:
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
    finally:
        _release_single_instance()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _log_crash(e)
        raise
