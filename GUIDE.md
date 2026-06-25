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
   iPhone (Shortcuts)  ─┐                          ┌─  Windows client (tray app)
                        ├──►   SERVER (port 5088)  ◄─┤
   Any web browser     ─┘      stores history       └─  Web interface (browser)
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
- **History…**: browse the server and local history; re-use or delete items.

To start the client automatically with Windows, press `Win+R`, type `shell:startup`, and
put a shortcut to the executable in that folder.

---

## 5. Set up iPhone Shortcuts

Open the **Shortcuts** app and create the shortcuts below. Each uses the built‑in
**Get Contents of URL** action. If your server uses a token, add a **Header** named
`X-Auth-Token` with the value `YOUR_TOKEN` in every shortcut.

### 5.1 Send text to the server
1. Tap **+** → **Add Action**.
2. Add **Get Clipboard**.
3. Add **Get Contents of URL**, then tap **Show More**:
   - URL: `http://SERVER_IP:5088/clipboard/text`
   - Method: **POST**
   - Request Body: **JSON** → add a field, type *Text*, key `text`, value = the
     **Clipboard** variable.
4. Rename it (e.g. "Send to PC"). Optionally add it to the Home Screen.

### 5.2 Receive text from the server
1. Tap **+** → add **Get Contents of URL**:
   - URL: `http://SERVER_IP:5088/clipboard/text/raw`
   - Method: **GET**
2. Add **Copy to Clipboard** (it uses the previous result).
3. Rename it (e.g. "Get from PC"). Now run it and paste anywhere.

### 5.3 Send a photo or file
1. Tap **+**, open the shortcut settings and enable **Show in Share Sheet**
   (accept *Images* and *Files*).
2. Add **Get Contents of URL**:
   - URL: `http://SERVER_IP:5088/clipboard/image`
   - Method: **POST**
   - Request Body: **File** → set it to **Shortcut Input**.
3. Now open Photos or Files, tap **Share**, and choose this shortcut.

### 5.4 Receive the latest image
1. Tap **+** → add **Get Contents of URL**:
   - URL: `http://SERVER_IP:5088/clipboard/image/latest/raw`
   - Method: **GET**
2. Add **Save to Photo Album** (or **Quick Look** to preview).

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

> The token travels in plain text over HTTP, which is fine on a trusted LAN. To use the
> server over the internet, put it behind a VPN or an HTTPS reverse proxy.

---

## 8. Troubleshooting

| Problem | Check |
|---------|-------|
| The web page won't open | Is the server running? Right `SERVER_IP`? Same network? Port 5088 allowed in the firewall? |
| `401 unauthorized` | The token is missing or wrong (`X-Auth-Token` / Settings → Token). |
| iPhone shortcut fails | Verify the URL and method; if you use a token, the header must be present. |
| A received image isn't on the Windows clipboard | Some apps only accept certain formats; the client copies images as bitmap (works in Office, Paint, chats). |
| Duplicate tray icons | Make sure only one instance of the client is running (close extra ones from Task Manager). |
