# Clipboard Bridge — Setup & Usage Guide

A step-by-step guide to install and use Clipboard Bridge.

Throughout this guide, replace the placeholders with your own values:

| Placeholder | Meaning | Example |
|-------------|---------|---------|
| `SERVER_IP` | local IP address of the computer running the server | `192.168.1.50` |
| `YOUR_TOKEN` | the optional security token (only if you set one) | `my-secret-123` |

## Contents
1. [How it works](#1-how-it-works)
2. [Before you start](#2-before-you-start)
3. [Set up the server](#3-set-up-the-server)
4. [Set up the Windows client](#4-set-up-the-windows-client)
5. [Set up iPhone Shortcuts](#5-set-up-iphone-shortcuts)
6. [Use the web interface](#6-use-the-web-interface)
7. [Security (optional token)](#7-security-optional-token)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. How it works

A small **server** keeps the last items you copied (text, images, files). Any device on
the same network can **send** items to it or **receive** the latest one, over plain HTTP.

```
   iPhone (Shortcuts)  ─┐                            ┌─  Windows client (tray app)
                        ├──►   SERVER (port 5088)  ◄─┤
   Any web browser     ─┘      stores history        └─  Web interface (browser)
```

There is no cloud and no account: everything stays on your local network.

---

## 2. Before you start

- A computer to run the server. It can be **Windows, macOS, Linux, a Raspberry Pi or a
  NAS** — anything that runs Python or Docker. It should stay on while you use the app.
- **Python 3.8+** (to run from source) or **Docker** (to run in a container).
- All your devices on the **same local network** (same Wi‑Fi/LAN).

### Find your server's IP address (`SERVER_IP`)
- **Windows**: open *Command Prompt*, run `ipconfig`, read the **IPv4 Address**
  (e.g. `192.168.1.50`).
- **macOS / Linux**: run `ip addr` (or `ifconfig`), or check your network settings.
- Or open your router's admin page and look at connected devices.

You will use this address (with port `5088`) on every other device.

---

## 3. Set up the server

### Option A — Run with Python
```bash
pip install -r requirements-server.txt
python clipboard_bridge-Server.py
```

### Option B — Run with Docker
```bash
docker compose up -d --build
```
The history is saved in the `./data` folder and survives restarts.

### Verify it works
On any device, open a browser and go to:
```
http://SERVER_IP:5088/
```
You should see the Clipboard Bridge web page. If it doesn't load, see
[Troubleshooting](#8-troubleshooting).

> **Tip:** on the first run, allow port `5088` through the server's firewall for the
> *private* network.

---

## 4. Set up the Windows client

### Option A — Executable
Build it once with `build_client.bat` (requires Python), then run
`dist\Clipboard Bridge.exe`. No installation needed.

### Option B — From source
```bash
pip install -r requirements-client.txt
python clipboard_bridge_windows.py
```

### Configure
A clipboard icon appears in the system tray (bottom‑right). Right‑click it:
1. Open **Settings…**
2. Set **Server IP** = `SERVER_IP`, **Port** = `5088`.
3. If your server uses a token, set **Token** = `YOUR_TOKEN`.
4. Choose your interface language from the **Language** menu (English / Italiano).

### Daily use
- **Send clipboard → server**: uploads whatever you copied (text, an image, or files
  selected in File Explorer). Also bound to `Ctrl+Alt+C` by default.
- **Receive latest ← server**: puts the latest item back on your clipboard (files are
  saved to the `ricevuti` folder). Also bound to `Ctrl+Alt+V`.
- **Send a file…**: pick any file(s) to upload.
- **Auto-sync** (tray menu, off by default): when enabled, anything you copy — text,
  images **and files** — is sent to the server automatically, without clicking.
- **History…**: browse the server and local history; re-use or delete items.

### Modes: connect to a server, or BE the server
Right-click the tray icon → **Mode**:
- **Client (use external server)** — the default; connects to a separate Clipboard Bridge
  server (set its address in Settings).
- **Server (this PC)** — no external server needed: this PC becomes the server and the
  iPhone connects to it directly on the local network. A **Server: `<ip>:<port>`** entry
  appears in the tray menu (click it to copy the address); use that address in your iPhone
  shortcuts instead of `SERVER_IP`. The port is `5088` by default and can be changed in
  Settings. In this mode only the essentials run (history + the latest text/image/file);
  there is no web page.

> The first time you enable Server mode, allow the app through the Windows firewall on the
> private network so the iPhone can reach it.

To start the client automatically with Windows, press `Win+R`, type `shell:startup`, and
put a shortcut to the executable in that folder.

---

## 5. Set up iPhone Shortcuts

You only need **two** shortcuts. They make no distinction between text and photos: they
always send, or fetch, the **most recent** item. Both use the built-in **Get Contents of
URL** action. If your server uses a token, add a **Header** `X-Auth-Token` = `YOUR_TOKEN`
to each shortcut.

### 5.1 Send (clipboard → server)
1. Open **Shortcuts**, tap **+** → **Add Action**.
2. Add **Get Clipboard**.
3. Add **Get Contents of URL**, then tap **Show More**:
   - URL: `http://SERVER_IP:5088/clipboard`
   - Method: **POST**
   - Request Body: **File** → set it to the **Clipboard** variable.
4. Name it (e.g. "Send") and add it to the Home Screen for one-tap use.

Copy anything — text or a photo — and run it: it is sent to the server as is.

### 5.2 Receive (server → clipboard)
1. Tap **+** → add **Get Contents of URL**:
   - URL: `http://SERVER_IP:5088/clipboard/latest/raw`
   - Method: **GET**
2. Add **Copy to Clipboard** (it uses the result).
3. Name it (e.g. "Receive"). Run it, then paste anywhere.

It always copies the latest item from the server — text or photo — to your clipboard.

> **Optional — other file types:** these two shortcuts cover text and photos through the
> clipboard. To send an arbitrary file, make a Share-Sheet shortcut that POSTs the file to
> `http://SERVER_IP:5088/clipboard`; to receive one, GET
> `http://SERVER_IP:5088/clipboard/latest/raw` and use **Save File** instead of Copy to Clipboard.

---

## 6. Use the web interface

You don't even need the client or Shortcuts: open `http://SERVER_IP:5088/` in any browser
(including Safari on the iPhone). From there you can:
- paste and save text,
- upload and download files,
- browse and clear the history,
- switch language with the **EN / IT** toggle.

With a token, open `http://SERVER_IP:5088/?token=YOUR_TOKEN`.

---

## 7. Security (optional token)

By default the server is open to anyone on your local network. To require a password‑like
token, start the server with the `CLIPBOARD_TOKEN` environment variable:

```bash
# Linux/macOS
CLIPBOARD_TOKEN=YOUR_TOKEN python clipboard_bridge-Server.py
```
```powershell
# Windows PowerShell
$env:CLIPBOARD_TOKEN="YOUR_TOKEN"; python clipboard_bridge-Server.py
```
With Docker, uncomment the `CLIPBOARD_TOKEN` line in `docker-compose.yml`.

Then provide the same token in the Windows client (Settings → Token) and in the iPhone
shortcuts (header `X-Auth-Token`).

### Password for the web page
The token protects the API; to also protect the **web page** with a login, set
`CLIPBOARD_PASSWORD`:
```bash
CLIPBOARD_PASSWORD=YOUR_PASSWORD python clipboard_bridge-Server.py
```
Opening the page now shows a login form; after you enter the password once, that device
stays logged in for a long time (a persistent session cookie). This applies only to the
external server's web page (the Windows "server mode" has no web page).

> The token and password travel in plain text over HTTP, which is fine on a trusted LAN. To
> use the server over the internet, put it behind a VPN or an HTTPS reverse proxy.

---

## 8. Troubleshooting

| Problem | Check |
|---------|-------|
| The web page won't open | Is the server running? Right `SERVER_IP`? Same network? Port 5088 allowed in the firewall? |
| `401 unauthorized` | The token is missing or wrong (`X-Auth-Token` / Settings → Token). |
| iPhone shortcut fails | Verify the URL and method; if you use a token, the header must be present. |
| A received image isn't on the Windows clipboard | Some apps only accept certain formats; the client copies images as bitmap (works in Office, Paint, chats). |
| Duplicate tray icons | Make sure only one instance of the client is running (close extra ones from Task Manager). |
