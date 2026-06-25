#!/usr/bin/env python3
"""
Clipboard Bridge - Server
=========================

Server HTTP (Flask) che fa da "ponte" per gli appunti tra Windows e iPhone
(tramite le Shortcuts/Comandi rapidi di iOS).

Caratteristiche:
  - Testo, immagini e file generici
  - Cronologia (history) con N elementi, file salvati su disco + index.json
  - Endpoint "raw" pensati per le Shortcuts (testo come text/plain, immagini come binario)
  - Token opzionale per proteggere il server (header X-Auth-Token oppure ?token=...)

Avvio:
    pip install flask
    python clipboard_bridge-Server.py

Configurazione tramite variabili d'ambiente (tutte opzionali):
    CLIPBOARD_PORT          porta di ascolto         (default 5088)
    CLIPBOARD_TOKEN         token di sicurezza       (default: vuoto = nessuna auth)
    CLIPBOARD_MAX_HISTORY   n. max elementi storico  (default 200)
    CLIPBOARD_DATA_DIR      cartella dei dati        (default ./clipboard_data)

Esempio con token (PowerShell):
    $env:CLIPBOARD_TOKEN="ilmiosegreto"; python clipboard_bridge-Server.py
"""

from flask import Flask, request, jsonify, Response, send_file, redirect
from markupsafe import escape
import base64
import os
import json
import time
import uuid
import mimetypes
import threading
from datetime import datetime

app = Flask(__name__)

# ---------- Configurazione ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("CLIPBOARD_DATA_DIR", os.path.join(BASE_DIR, "clipboard_data"))
ITEMS_DIR = os.path.join(DATA_DIR, "items")
INDEX_FILE = os.path.join(DATA_DIR, "index.json")

PORT = int(os.environ.get("CLIPBOARD_PORT", "5088"))
AUTH_TOKEN = os.environ.get("CLIPBOARD_TOKEN", "").strip()
MAX_HISTORY = int(os.environ.get("CLIPBOARD_MAX_HISTORY", "200"))

os.makedirs(ITEMS_DIR, exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64 MB per richiesta

_lock = threading.Lock()


# ---------- Gestione indice / storico ----------
def _load_index():
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_index(index):
    tmp = INDEX_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    os.replace(tmp, INDEX_FILE)  # scrittura atomica


def _trim(index):
    """Mantiene al massimo MAX_HISTORY elementi, cancellando i file dei più vecchi."""
    while len(index) > MAX_HISTORY:
        old = index.pop()
        fname = old.get("file")
        if fname:
            try:
                os.remove(os.path.join(ITEMS_DIR, fname))
            except OSError:
                pass


def _meta(entry):
    """Restituisce solo i metadati (senza contenuto) di un elemento."""
    return {k: entry.get(k) for k in
            ("id", "type", "timestamp", "filename", "mime", "size", "preview")}


def _read_text(entry):
    path = os.path.join(ITEMS_DIR, entry["file"])
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def _entry_with_content(entry):
    """Metadati + contenuto: 'text' per il testo, 'data' (base64) per binari."""
    out = _meta(entry)
    if entry["type"] == "text":
        out["text"] = _read_text(entry)
    else:
        path = os.path.join(ITEMS_DIR, entry["file"])
        with open(path, "rb") as f:
            out["data"] = base64.b64encode(f.read()).decode()
    return out


def _latest_of(types):
    for e in _load_index():
        if e["type"] in types:
            return e
    return None


def _add_text(text):
    entry_id = uuid.uuid4().hex[:12]
    fname = entry_id + ".txt"
    with open(os.path.join(ITEMS_DIR, fname), "w", encoding="utf-8") as f:
        f.write(text)
    entry = {
        "id": entry_id,
        "type": "text",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ts": time.time(),
        "file": fname,
        "filename": None,
        "mime": "text/plain",
        "size": len(text.encode("utf-8")),
        "preview": text[:140],
    }
    with _lock:
        index = _load_index()
        index.insert(0, entry)
        _trim(index)
        _save_index(index)
    return entry


def _add_binary(raw, orig_filename=None, mime=None):
    entry_id = uuid.uuid4().hex[:12]
    # Estensione: dal nome file originale, altrimenti dal mime
    ext = ""
    if orig_filename and "." in orig_filename:
        ext = "." + orig_filename.rsplit(".", 1)[1].lower()
    elif mime:
        ext = mimetypes.guess_extension(mime) or ""
    fname = entry_id + (ext or ".bin")
    with open(os.path.join(ITEMS_DIR, fname), "wb") as f:
        f.write(raw)

    if not mime:
        mime = mimetypes.guess_type(orig_filename or fname)[0] or "application/octet-stream"
    is_image = mime.startswith("image/")
    entry = {
        "id": entry_id,
        "type": "image" if is_image else "file",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ts": time.time(),
        "file": fname,
        "filename": orig_filename or fname,
        "mime": mime,
        "size": len(raw),
        "preview": orig_filename or fname,
    }
    with _lock:
        index = _load_index()
        index.insert(0, entry)
        _trim(index)
        _save_index(index)
    return entry


# ---------- Estrazione dati dalle richieste ----------
def _get_posted_text():
    """Accetta JSON {text:...}, form 'text=...' oppure corpo grezzo (text/plain)."""
    if request.is_json:
        data = request.get_json(silent=True) or {}
        return data.get("text", "")
    if request.form and "text" in request.form:
        return request.form.get("text", "")
    raw = request.get_data(cache=False)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def _extract_upload():
    """
    Estrae (bytes, filename, mime) da:
      - multipart/form-data (campo file qualsiasi)
      - JSON {filename, data(base64), mime}
      - corpo binario grezzo (Content-Type immagine, header X-Filename opzionale)
    """
    if request.files:
        f = next(iter(request.files.values()))
        return f.read(), f.filename, (f.mimetype or None)

    if request.is_json:
        data = request.get_json(silent=True) or {}
        b64 = (data.get("data") or "").replace("\n", "").replace("\r", "")
        if not b64:
            return None, None, None
        try:
            raw = base64.b64decode(b64)
        except (ValueError, base64.binascii.Error):
            return None, None, None
        return raw, data.get("filename"), data.get("mime")

    raw = request.get_data(cache=False)
    if raw:
        mime = request.headers.get("Content-Type")
        if mime and ";" in mime:
            mime = mime.split(";")[0].strip()
        return raw, request.headers.get("X-Filename"), mime
    return None, None, None


# ---------- Autenticazione (opzionale) ----------
@app.before_request
def _check_auth():
    if not AUTH_TOKEN:
        return  # auth disabilitata
    if request.path == "/health":
        return  # endpoint pubblici per il diagnostico
    token = request.headers.get("X-Auth-Token") or request.args.get("token", "")
    if token != AUTH_TOKEN:
        return jsonify({"error": "unauthorized"}), 401


# ---------- TESTO ----------
@app.route("/clipboard/text", methods=["GET", "POST"])
def clipboard_text():
    if request.method == "POST":
        entry = _add_text(_get_posted_text())
        return jsonify({"status": "ok", "id": entry["id"]})
    # GET -> ultimo testo (compatibile con il vecchio client)
    e = _latest_of(("text",))
    return jsonify({"text": _read_text(e) if e else ""})


@app.route("/clipboard/text/raw", methods=["GET"])
def clipboard_text_raw():
    """Testo puro (text/plain): comodo per incollare nelle Shortcuts."""
    e = _latest_of(("text",))
    return Response(_read_text(e) if e else "", mimetype="text/plain")


# ---------- IMMAGINI ----------
@app.route("/clipboard/image", methods=["POST"])
def push_image():
    raw, filename, mime = _extract_upload()
    if raw is None:
        return jsonify({"error": "nessun dato immagine"}), 400
    if not mime:
        mime = "image/png"
    if not filename:
        filename = "clipboard" + (mimetypes.guess_extension(mime) or ".png")
    entry = _add_binary(raw, filename, mime)
    return jsonify({"status": "ok", "id": entry["id"], "filename": entry["filename"]})


@app.route("/clipboard/image/latest", methods=["GET"])
def image_latest():
    e = _latest_of(("image",))
    if not e:
        return jsonify({"error": "no images"}), 404
    with open(os.path.join(ITEMS_DIR, e["file"]), "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return jsonify({"filename": e["filename"], "data": b64, "mime": e["mime"], "id": e["id"]})


@app.route("/clipboard/image/latest/raw", methods=["GET"])
def image_latest_raw():
    """Immagine come binario: le Shortcuts la ricevono direttamente come foto."""
    e = _latest_of(("image",))
    if not e:
        return jsonify({"error": "no images"}), 404
    return send_file(os.path.join(ITEMS_DIR, e["file"]),
                     mimetype=e["mime"], download_name=e["filename"])


# ---------- FILE GENERICI (retro-compatibilità) ----------
@app.route("/clipboard/file", methods=["POST"])
def push_file():
    content = request.get_json(silent=True) or {}
    filename = content.get("filename")
    b64 = (content.get("data") or "").replace("\n", "").replace("\r", "")
    if not filename or not b64:
        return jsonify({"error": "filename o data mancante"}), 400
    try:
        raw = base64.b64decode(b64)
    except (ValueError, base64.binascii.Error):
        return jsonify({"error": "base64 non valido"}), 400
    entry = _add_binary(raw, filename, mimetypes.guess_type(filename)[0])
    return jsonify({"status": "ok", "saved": entry["filename"], "id": entry["id"]})


@app.route("/clipboard/file/latest", methods=["GET"])
def file_latest():
    e = _latest_of(("image", "file"))
    if not e:
        return jsonify({"error": "no files"}), 404
    with open(os.path.join(ITEMS_DIR, e["file"]), "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return jsonify({"filename": e["filename"], "data": b64})


# ---------- UNIVERSALE / STORICO ----------
@app.route("/clipboard/latest", methods=["GET"])
def latest_any():
    """Ultimo elemento di qualsiasi tipo, contenuto incluso."""
    index = _load_index()
    if not index:
        return jsonify({"type": "empty"})
    return jsonify(_entry_with_content(index[0]))


@app.route("/clipboard/history", methods=["GET", "DELETE"])
def history():
    if request.method == "DELETE":
        with _lock:
            for e in _load_index():
                try:
                    os.remove(os.path.join(ITEMS_DIR, e["file"]))
                except OSError:
                    pass
            _save_index([])
        return jsonify({"status": "cleared"})

    index = _load_index()
    type_filter = request.args.get("type")
    if type_filter:
        index = [e for e in index if e["type"] == type_filter]
    limit = request.args.get("limit", type=int)
    if limit:
        index = index[:limit]
    return jsonify({"items": [_meta(e) for e in index], "count": len(index)})


@app.route("/clipboard/item/<item_id>", methods=["GET", "DELETE"])
def item(item_id):
    e = next((x for x in _load_index() if x["id"] == item_id), None)
    if not e:
        return jsonify({"error": "not found"}), 404
    if request.method == "DELETE":
        with _lock:
            index = [x for x in _load_index() if x["id"] != item_id]
            _save_index(index)
        try:
            os.remove(os.path.join(ITEMS_DIR, e["file"]))
        except OSError:
            pass
        return jsonify({"status": "deleted"})
    return jsonify(_entry_with_content(e))


@app.route("/clipboard/item/<item_id>/raw", methods=["GET"])
def item_raw(item_id):
    e = next((x for x in _load_index() if x["id"] == item_id), None)
    if not e:
        return jsonify({"error": "not found"}), 404
    if e["type"] == "text":
        return Response(_read_text(e), mimetype="text/plain")
    return send_file(os.path.join(ITEMS_DIR, e["file"]),
                     mimetype=e["mime"], download_name=e["filename"])


# ---------- Diagnostica ----------
@app.route("/health")
def health():
    return jsonify({"status": "ok", "items": len(_load_index()), "auth": bool(AUTH_TOKEN)})


# Logo e icone inline (SVG): nessuna immagine esterna, funziona offline.
LOGO_SVG = ('<svg class="logo" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">'
            '<rect x="9" y="6" width="30" height="38" rx="6" fill="#4f46e5"/>'
            '<rect x="14" y="11" width="20" height="28" rx="3" fill="#ffffff"/>'
            '<rect x="18" y="3" width="12" height="9" rx="3" fill="#94a3b8"/>'
            '<rect x="18.5" y="17" width="13" height="2.6" rx="1.3" fill="#4f46e5"/>'
            '<rect x="18.5" y="23" width="11" height="2.4" rx="1.2" fill="#cbd5e1"/>'
            '<rect x="18.5" y="28.5" width="11" height="2.4" rx="1.2" fill="#cbd5e1"/></svg>')

_S = ('viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
      'stroke-linecap="round" stroke-linejoin="round"')
IC_TEXT = f'<svg {_S}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/></svg>'
IC_FILE = f'<svg {_S}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/></svg>'
IC_UP = f'<svg {_S}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 9l5-5 5 5"/><path d="M12 4v12"/></svg>'
IC_HIST = f'<svg {_S}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>'
IC_PHONE = f'<svg {_S}><rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/></svg>'

_HOME_CSS = """
*{box-sizing:border-box}
body{margin:0;background:linear-gradient(180deg,#eef2ff,#f8fafc 260px);
 font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#1e293b}
.wrap{max-width:760px;margin:0 auto;padding:22px 16px 50px}
.head{display:flex;align-items:center;gap:14px;margin:6px 0 18px}
.logo{width:46px;height:46px;flex:0 0 auto}
.head h1{font-size:21px;margin:0}.head p{margin:2px 0 0;color:#64748b;font-size:13px}
.badge{margin-left:auto;background:#dcfce7;color:#166534;border:1px solid #bbf7d0;
 padding:6px 11px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:18px;margin:16px 0;
 box-shadow:0 1px 2px rgba(15,23,42,.04),0 10px 30px -20px rgba(15,23,42,.25)}
.card h2{display:flex;align-items:center;gap:8px;font-size:15px;margin:0 0 12px}
.card h2 svg{width:18px;height:18px;color:#4f46e5;flex:0 0 auto}
textarea{width:100%;border:1px solid #e2e8f0;border-radius:10px;padding:12px;font:inherit;
 font-size:15px;resize:vertical;min-height:120px;background:#f8fafc}
.row{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
.btn{border:0;background:#4f46e5;color:#fff;padding:10px 16px;border-radius:10px;font-size:14px;
 font-weight:600;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center}
.btn:hover{background:#4338ca}
.btn.ghost{background:#f1f5f9;color:#334155;border:1px solid #e2e8f0}
.btn.ghost:hover{background:#e2e8f0}
.btn.small{padding:6px 10px;font-size:12px;border-radius:8px}
.drop{border:2px dashed #c7d2fe;border-radius:12px;padding:24px;text-align:center;color:#64748b;
 background:#f8fafc;cursor:pointer;transition:.15s}
.drop.hover{border-color:#4f46e5;background:#eef2ff;color:#4f46e5}
.item{display:flex;align-items:center;gap:12px;padding:10px 0;border-top:1px solid #eef2f7}
.item:first-child{border-top:0}
.thumb{width:44px;height:44px;border-radius:9px;object-fit:cover;border:1px solid #e2e8f0;background:#fff;flex:0 0 auto}
.ico{width:44px;height:44px;border-radius:9px;display:flex;align-items:center;justify-content:center;
 background:#eef2ff;color:#4f46e5;flex:0 0 auto}.ico svg{width:22px;height:22px}
.meta{flex:1;min-width:0}.prev{font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sub{font-size:12px;color:#94a3b8;margin-top:2px}
.actions{display:flex;gap:6px;flex:0 0 auto}
.empty{color:#94a3b8;font-size:14px;padding:6px 0}
.url{display:flex;align-items:center;gap:10px;background:#f8fafc;border:1px solid #e2e8f0;
 border-radius:9px;padding:8px 10px;margin:4px 0 10px}
.url code{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
 font-size:12.5px;color:#334155;background:transparent;padding:0}
.method{font-weight:700;color:#4f46e5;font-size:11px;background:#eef2ff;padding:3px 8px;border-radius:6px}
code{background:#eef2ff;padding:2px 6px;border-radius:5px;font-size:13px}
.nota{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;padding:10px 12px;
 border-radius:10px;font-size:13px;margin:0 0 10px}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:#111827;color:#fff;
 padding:10px 18px;border-radius:10px;font-size:13px;opacity:0;transition:.2s;pointer-events:none}
.toast.show{opacity:1}.foot{text-align:center;color:#94a3b8;font-size:12px;margin-top:8px}
.lang{margin-top:6px;font-size:12px}
.lang a{color:#94a3b8;text-decoration:none;padding:0 3px}
.lang a.on{color:#4f46e5;font-weight:700}
"""

_HOME_JS = """
function toast(m){var t=document.getElementById('toast');t.textContent=m;t.classList.add('show');
clearTimeout(window._t);window._t=setTimeout(function(){t.classList.remove('show');},1400);}
function copia(s){var a=document.createElement('textarea');a.value=s;a.style.position='fixed';
a.style.opacity='0';document.body.appendChild(a);a.focus();a.select();
try{document.execCommand('copy');}catch(e){}document.body.removeChild(a);toast(T_COPIED);}
function elimina(id){if(!confirm(T_DEL))return;
fetch('/clipboard/item/'+id+TOKENQS,{method:'DELETE'}).then(function(){location.reload();});}
function svuota(){if(!confirm(T_CLEAR))return;
fetch('/clipboard/history'+TOKENQS,{method:'DELETE'}).then(function(){location.reload();});}
(function(){var z=document.getElementById('drop'),f=document.getElementById('file'),
fm=document.getElementById('upform');if(!z)return;z.onclick=function(){f.click();};
function on(e){e.preventDefault();z.classList.add('hover');}
function off(e){e.preventDefault();z.classList.remove('hover');}
z.addEventListener('dragover',on);z.addEventListener('dragenter',on);z.addEventListener('dragleave',off);
z.addEventListener('drop',function(e){off(e);if(e.dataTransfer.files.length){f.files=e.dataTransfer.files;fm.submit();}});
f.addEventListener('change',function(){if(f.files.length)fm.submit();});})();
"""


def _human(n):
    n = float(n or 0)
    for u in ("B", "KB", "MB"):
        if n < 1024:
            return f"{int(n)} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} GB"


def _urlrow(method, url, copy_label):
    return (f'<div class="url"><span class="method">{method}</span>'
            f'<code>{escape(url)}</code>'
            f"<button class=\"btn small ghost\" type=\"button\" onclick=\"copia('{url}')\">{copy_label}</button></div>")


def _ui_token():
    return request.args.get("token", "")


def _ui_lang():
    lang = request.args.get("lang", "en")
    return lang if lang in ("en", "it") else "en"


def _home_url():
    tok = _ui_token()
    return "/?lang=" + _ui_lang() + (("&token=" + tok) if tok else "")


WEB_STRINGS = {
    "en": {
        "subtitle": "Share text and files across your devices",
        "online": "Online &middot; {n} in history",
        "h_text": "Text", "ph_text": "Type or paste the text to share here...",
        "save": "Save to server", "copy": "Copy",
        "h_file": "File", "drop1": "Drop files here", "drop2": "or click to choose them",
        "upload": "Upload",
        "h_history": "History", "refresh": "Refresh", "clear": "Clear",
        "download": "Download", "delete": "Delete",
        "empty": "Nothing yet. Save some text or upload a file above.",
        "no_preview": "(no preview)",
        "h_iphone": "iPhone (Shortcuts)",
        "iphone_intro": "Use the “Get Contents of URL” action with these addresses:",
        "ip_send_text": "Send text", "ip_send_text_sub": "JSON body, field",
        "ip_recv_text": "Receive text", "ip_recv_text_sub": "&rarr; Copy to clipboard",
        "ip_send_file": "Send photo or file", "ip_send_file_sub": "body: File",
        "ip_recv_img": "Receive latest image", "ip_recv_img_sub": "&rarr; Save to album",
        "token_note": "Token enabled: in the Shortcuts add the header",
        "foot": "This page also works from the iPhone browser.",
        "js_copied": "Copied to the clipboard", "js_del": "Delete this item?",
        "js_clear": "Clear the whole history?",
    },
    "it": {
        "subtitle": "Condividi testo e file tra i tuoi dispositivi",
        "online": "Online &middot; {n} in cronologia",
        "h_text": "Testo", "ph_text": "Scrivi o incolla qui il testo da condividere...",
        "save": "Salva sul server", "copy": "Copia",
        "h_file": "File", "drop1": "Trascina qui i file", "drop2": "oppure clicca per sceglierli",
        "upload": "Carica",
        "h_history": "Cronologia", "refresh": "Aggiorna", "clear": "Svuota",
        "download": "Scarica", "delete": "Elimina",
        "empty": "Ancora niente. Salva del testo o carica un file qui sopra.",
        "no_preview": "(senza anteprima)",
        "h_iphone": "iPhone (Comandi rapidi)",
        "iphone_intro": "Usa l’azione «Ottieni contenuto dell’URL» con questi indirizzi:",
        "ip_send_text": "Invia testo", "ip_send_text_sub": "corpo JSON, campo",
        "ip_recv_text": "Ricevi testo", "ip_recv_text_sub": "&rarr; Copia negli appunti",
        "ip_send_file": "Invia foto o file", "ip_send_file_sub": "corpo: File",
        "ip_recv_img": "Ricevi ultima immagine", "ip_recv_img_sub": "&rarr; Salva nell’album",
        "token_note": "Token attivo: nelle Shortcut aggiungi l’intestazione",
        "foot": "Questa pagina funziona anche dal browser dell’iPhone.",
        "js_copied": "Copiato negli appunti", "js_del": "Eliminare questo elemento?",
        "js_clear": "Svuotare tutta la cronologia?",
    },
}


def render_home():
    tok = _ui_token()
    lang = _ui_lang()
    S = WEB_STRINGS[lang]
    tq = ("?token=" + tok) if tok else ""                       # token only (raw / API / img)
    fq = "?lang=" + lang + (("&token=" + tok) if tok else "")   # forms / redirect (lang + token)
    base = request.host_url.rstrip("/")

    e = _latest_of(("text",))
    latest_text = _read_text(e) if e else ""

    items = _load_index()
    rows = ""
    for it in items[:20]:
        tid, kind = it["id"], it["type"]
        prev = escape(it.get("preview") or S["no_preview"])
        sub = f'{kind} &middot; {_human(it.get("size"))} &middot; {escape(it.get("timestamp") or "")}'
        if kind == "image":
            media = f'<img class="thumb" src="/clipboard/item/{tid}/raw{tq}" alt="">'
        else:
            media = f'<span class="ico">{IC_FILE if kind == "file" else IC_TEXT}</span>'
        rows += (f'<div class="item">{media}'
                 f'<div class="meta"><div class="prev">{prev}</div><div class="sub">{sub}</div></div>'
                 f'<div class="actions">'
                 f'<a class="btn small ghost" href="/clipboard/item/{tid}/raw{tq}">{S["download"]}</a>'
                 f"<button class=\"btn small ghost\" type=\"button\" onclick=\"elimina('{tid}')\">{S['delete']}</button>"
                 f'</div></div>')
    if not rows:
        rows = f'<div class="empty">{S["empty"]}</div>'

    nota = ""
    if tok:
        nota = (f'<div class="nota">{S["token_note"]} '
                f'<code>X-Auth-Token: {escape(tok)}</code>.</div>')

    en_href = "/?lang=en" + (("&token=" + tok) if tok else "")
    it_href = "/?lang=it" + (("&token=" + tok) if tok else "")
    en_on = "on" if lang == "en" else ""
    it_on = "on" if lang == "it" else ""
    lang_toggle = (f'<div class="lang"><a href="{en_href}" class="{en_on}">EN</a>'
                   f'<a href="{it_href}" class="{it_on}">IT</a></div>')

    js_consts = (f'const TOKENQS="{tq}";const T_COPIED="{S["js_copied"]}";'
                 f'const T_DEL="{S["js_del"]}";const T_CLEAR="{S["js_clear"]}";')

    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clipboard Bridge</title><style>{_HOME_CSS}</style></head>
<body><div class="wrap">

<div class="head">{LOGO_SVG}
<div><h1>Clipboard Bridge</h1><p>{S["subtitle"]}</p></div>
<div style="margin-left:auto;text-align:right"><span class="badge">&#9679; {S["online"].format(n=len(items))}</span>{lang_toggle}</div></div>

<div class="card">
<h2>{IC_TEXT} {S["h_text"]}</h2>
<form method="post" action="/ui/text{fq}">
<textarea id="txt" name="text" placeholder="{S["ph_text"]}">{escape(latest_text)}</textarea>
<div class="row">
<button class="btn" type="submit">{S["save"]}</button>
<button class="btn ghost" type="button" onclick="copia(document.getElementById('txt').value)">{S["copy"]}</button>
</div>
</form>
</div>

<div class="card">
<h2>{IC_UP} {S["h_file"]}</h2>
<form id="upform" method="post" action="/ui/upload{fq}" enctype="multipart/form-data">
<div class="drop" id="drop">{S["drop1"]}<br><b>{S["drop2"]}</b></div>
<input id="file" type="file" name="file" multiple style="display:none">
<div class="row"><button class="btn" type="submit">{S["upload"]}</button></div>
</form>
</div>

<div class="card">
<h2>{IC_HIST} {S["h_history"]} <span style="margin-left:auto;display:flex;gap:6px"><button class="btn small ghost" type="button" onclick="location.reload()">{S["refresh"]}</button><button class="btn small ghost" type="button" onclick="svuota()">{S["clear"]}</button></span></h2>
{rows}
</div>

<div class="card">
<h2>{IC_PHONE} {S["h_iphone"]}</h2>
{nota}
<p style="color:#64748b;font-size:13px;margin:0 0 8px">{S["iphone_intro"]}</p>
<div style="font-size:13px"><b>{S["ip_send_text"]}</b> &middot; {S["ip_send_text_sub"]} <code>text</code></div>
{_urlrow("POST", base + "/clipboard/text", S["copy"])}
<div style="font-size:13px"><b>{S["ip_recv_text"]}</b> {S["ip_recv_text_sub"]}</div>
{_urlrow("GET", base + "/clipboard/text/raw" + tq, S["copy"])}
<div style="font-size:13px"><b>{S["ip_send_file"]}</b> &middot; {S["ip_send_file_sub"]}</div>
{_urlrow("POST", base + "/clipboard/image", S["copy"])}
<div style="font-size:13px"><b>{S["ip_recv_img"]}</b> {S["ip_recv_img_sub"]}</div>
{_urlrow("GET", base + "/clipboard/image/latest/raw" + tq, S["copy"])}
</div>

<div class="foot">{S["foot"]}</div>
</div>
<div id="toast" class="toast"></div>
<script>{js_consts}{_HOME_JS}</script>
</body></html>"""


@app.route("/")
def home():
    return Response(render_home(), mimetype="text/html")


@app.route("/ui/text", methods=["POST"])
def ui_text():
    _add_text(request.form.get("text", ""))
    return redirect(_home_url())


@app.route("/ui/upload", methods=["POST"])
def ui_upload():
    for f in request.files.getlist("file"):
        if f and f.filename:
            _add_binary(f.read(), f.filename, f.mimetype or None)
    return redirect(_home_url())


if __name__ == "__main__":
    print("=" * 52)
    print(" Clipboard Bridge - Server")
    print(f"   In ascolto su:  http://0.0.0.0:{PORT}")
    print(f"   Cartella dati:  {DATA_DIR}")
    print(f"   Storico max:    {MAX_HISTORY} elementi")
    print(f"   Autenticazione: {'ATTIVA (token)' if AUTH_TOKEN else 'disattivata'}")
    print("=" * 52)
    app.run(host="0.0.0.0", port=PORT)
