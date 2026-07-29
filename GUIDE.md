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
Download the installer or portable EXE from the GitHub Release. To rebuild both universal
Windows packages locally, run `build_windows_release.bat 2.0.2` (requires Python,
PyInstaller and Inno Setup). No personal configuration is embedded in either package.
The installer uses the current user's LocalAppData folder and does not require
administrator privileges.

> **Windows 11 security:** version 2.0.2 is currently unsigned, so Smart App Control can
> block both the installer and portable executable. There is no per-app exception for
> Smart App Control. Trusted Authenticode signing is being prepared; see the
> [code signing policy](CODE_SIGNING.md).

### Option B — From source
```bash
pip install -r requirements-client.txt
python clipboard_bridge_windows.py
```

### Configure
A clipboard icon appears in the system tray (bottom‑right). Right‑click it:
1. Open **Settings…**
2. In **General**, choose Client/Server mode, interface language and the local-history limit.
3. In **Connection**, set **Server IP** = `SERVER_IP`, **Port** = `5088`.
4. If your server uses a token, set **Token** = `YOUR_TOKEN`.
5. Use **Automation** and **Shortcuts** for automatic transfers and configurable hotkeys.

### Daily use
- **Send clipboard → server**: uploads whatever you copied (text, an image, or files
  selected in File Explorer). Also bound to `Ctrl+Alt+C` by default.
- **Receive latest ← server**: puts the latest item back on your clipboard (files are
  saved to `Downloads\Clipboard Bridge` and copied as File Explorer files). Also bound to
  `Ctrl+Alt+V`.
- **Send a file…**: pick any file(s) to upload.
- **Auto-sync** (Settings → Automation, off by default): when enabled, anything you copy — text,
  images **and files** — is sent to the server automatically, without clicking.
- **Automatically download new files** (Settings, on by default): while the client is
  running, new PDFs and other files arrive without pressing Receive. Click the Windows
  notification to open File Explorer with the received file selected. The downloaded
  file is also placed on the Windows clipboard, ready to paste.
- **History…**: browse the server and local history; re-use or delete items.
- **Connection status**: the tray contains one compact green/red indicator. Settings show
  the detailed result and **Check connection now** after editing the address, token or
  account.
- **Single instance**: starting Clipboard Bridge again while it is already running exits
  immediately, so duplicate processes and tray icons are not created.

### Modes: connect to a server, or BE the server
Choose the mode from **Settings → General**:
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

The executable can safely remain in `Program Files`: Clipboard Bridge stores configuration,
history, Server-mode data and logs in `%LOCALAPPDATA%\Clipboard Bridge`. Received files are
stored in `%USERPROFILE%\Downloads\Clipboard Bridge`. Data from older versions found beside
the executable is copied automatically on first run. Version 2.0.2 also checks old
`Program Files` installations and can recover settings after a 2.0.1 default configuration
was created.

> **Auto-sync and administrator privileges:** this applies to both the installer and
> portable versions. Auto-sync may not detect clipboard changes made by applications that
> are themselves running as administrator. If this happens, right-click Clipboard Bridge
> and select **Run as administrator**.

---

## 5. Set up iPhone Shortcuts

You only need **two** shortcuts. They make no distinction between text and photos: they
always send, or fetch, the **most recent** item. Both use the built-in **Get Contents of
URL** action. If your server uses a token, add a **Header** `X-Auth-Token` = `YOUR_TOKEN`
to each shortcut.

### Download the ready-made Shortcuts

Both prepared iPhone Shortcuts are included in the
[Clipboard Bridge 2.0.2 release](https://github.com/mattbox03/Clipboard-Bridge/releases/tag/2.0.2):

- [Load Clipboard - send to the server](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.2/Load.Clipboard.shortcut)
- [Download Clipboard - receive the latest item](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.2/Download.Clipboard.shortcut)

Open the downloaded files on the iPhone, add them to the Shortcuts app and replace the
placeholder address with the server address displayed by Clipboard Bridge. If applicable,
also add the API token or append `?user=NAME&password=PASS` to the URL.

### Add both Shortcuts to Control Center

To run them without opening the Shortcuts app:

1. Open **Control Center** and tap the **Add (+)** button.
2. Tap **Add a Control**, select **Shortcut**, and tap **Choose**.
3. Choose **Load Clipboard**.
4. Add another Shortcut control and choose **Download Clipboard**.

You can now send or receive the latest item from the iPhone's pull-down Control Center.
Apple documents the same procedure in its
[Shortcuts User Guide](https://support.apple.com/guide/shortcuts/apd06a9201d4/ios).

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

### Multiple accounts
Besides the shared space, you can create separate, **isolated** spaces (each with its own
history) by listing `user:password` pairs in `CLIPBOARD_ACCOUNTS`:
```bash
CLIPBOARD_ACCOUNTS="alice:secret1,bob:secret2" python clipboard_bridge-Server.py
```
There is **no limit** on the number of accounts. For many users, put one `user:password`
per line in a file and point `CLIPBOARD_ACCOUNTS_FILE` to it instead:
```bash
CLIPBOARD_ACCOUNTS_FILE=/data/accounts.txt python clipboard_bridge-Server.py
```
To use an account, add its credentials at the **end of the URL** —
`...?user=alice&password=secret1` — in your iPhone Shortcuts, or fill the **Account** and
**Account password** fields in the Windows client Settings. On the web page, log in with the
account name (leave it empty for the shared space). The shared space is always available.
The URL format remains the recommended option for the two simple iPhone Shortcuts.
Other API clients can optionally use `X-Clipboard-User` and `X-Clipboard-Password`
headers instead.

> The token and password travel in plain text over HTTP, which is fine on a trusted LAN. To
> use the server away from that LAN, put it behind a VPN or an HTTPS reverse proxy.
> [Tailscale](https://tailscale.com/) is one possible VPN: install it on the iPhone and
> server, then replace `SERVER_IP` in both Shortcuts with the server's Tailscale IP
> (usually `100.x.y.z`). This includes the Windows app's **Server mode**: install Tailscale
> on that PC and use its Tailscale IP plus the port configured in Clipboard Bridge. No
> router port forwarding is required.

---

## 8. Troubleshooting

| Problem | Check |
|---------|-------|
| The web page won't open | Is the server running? Right `SERVER_IP`? Same network? Port 5088 allowed in the firewall? |
| `401 unauthorized` | The token is missing or wrong (`X-Auth-Token` / Settings → Token). |
| iPhone shortcut fails | Verify the URL and method; if you use a token, the header must be present. |
| A received image isn't on the Windows clipboard | Some apps only accept certain formats; the client copies images as bitmap (works in Office, Paint, chats). |
| Duplicate tray icons | Make sure only one instance of the client is running (close extra ones from Task Manager). |
