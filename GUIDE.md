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

Clipboard Bridge always stores the latest text, image or file in a server space. You can
choose between two distinct modes:

| Mode | What runs the server | Choose it when |
|------|----------------------|----------------|
| **Windows Server mode** | the Windows tray app itself | you want the fastest PC ↔ iPhone setup |
| **Client mode** | a separate Python/Docker server | you want an always-on service, web page or multiple accounts |

```
Windows Server mode:  iPhone (Shortcuts)  ⇄  Windows app

Client mode:          iPhone (Shortcuts)  ⇄  private server  ⇄  Windows app
```

There is no mandatory cloud service or online account. Optional server accounts are local
to your own installation.

> **Token and account authentication are optional.** Without either one, Clipboard
> Bridge uses the general shared space. URLs configured with `?token=...` or
> `?user=...&password=...` contain those values in plain text. HTTP does not encrypt
> them; keep the server on a trusted LAN/private VPN or use an HTTPS reverse proxy.

---

## 2. Before you start

- A **Windows 10/11 PC** and an iPhone with the Shortcuts app.
- All your devices on the **same local network** (same Wi‑Fi/LAN).
- Only for Client mode: a computer, NAS or Raspberry Pi for the separate server, with
  **Python 3.12** or **Docker**.

### Find your server's IP address (`SERVER_IP`)
- **Windows**: open *Command Prompt*, run `ipconfig`, read the **IPv4 Address**
  (e.g. `192.168.1.50`).
- **macOS / Linux**: run `ip addr` (or `ifconfig`), or check your network settings.
- Or open your router's admin page and look at connected devices.

You will use this address (with port `5088`) on every other device.

---

## 3. Set up the separate server (Client mode only)

Skip this section when using **Windows Server mode**.

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
Windows packages locally, run `build_windows_release.bat 2.0.6` (requires Python,
PyInstaller and Inno Setup). No personal configuration is embedded in either package.
The installer uses the current user's LocalAppData folder and does not require
administrator privileges.

> **Windows 11 security:** version 2.0.6 is currently unsigned, so Smart App Control can
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
2. In **General**, choose a mode:
   - **Server**: the app displays the address to place in the iPhone Shortcuts. No
     separate server is required.
   - **Client**: in **Connection**, set **Server IP** = `SERVER_IP` and **Port** = `5088`.
3. In Client mode, enter the optional token or account credentials configured by the
   server.
4. Click **Check connection now**. The detailed status must become **CONNECTED** and the
   compact tray status must turn green.
5. Use **Automation** and **Shortcuts** for automatic transfers and configurable hotkeys.

### Daily use
- **Send clipboard → server**: uploads whatever you copied (text, an image, or files
  selected in File Explorer). Also bound to `Ctrl+Alt+C` by default.
- **Receive latest ← server**: puts the latest item back on your clipboard (files are
  saved to `Downloads\Clipboard Bridge` and copied as File Explorer files). Also bound to
  `Ctrl+Alt+V`.
- **Send a file…**: pick any file(s) to upload.
  Files selected in the same operation remain one grouped history item. Windows and
  Android restore all members together; iPhone and generic HTTP clients download the
  group as one ZIP file.
- **Auto-sync** (Settings → Automation, off by default): when enabled, anything you copy — text,
  images **and files** — is sent to the server automatically, without clicking.
- **Automatically download new files** (Settings, on by default): while the client is
  running, new PDFs and other files arrive without pressing Receive. Click the Windows
  notification to open File Explorer with the received file selected. The downloaded
  file is also placed on the Windows clipboard, ready to paste.
- **Notifications** (Settings → Automation): use the main switch to disable every Windows
  notification, or choose independently whether received text, images and files should
  produce an alert. Automatically received text and images are copied to the clipboard
  before their notification appears.
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
  there is no web page. Its iPhone endpoints accept the same Unicode text, raw files,
  multipart uploads and JSON/Base64 payloads as the external server.

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
[Clipboard Bridge 2.0.6 release](https://github.com/Mattboxx/Clipboard-Bridge/releases/tag/2.0.6):

- [iPhone Load Clipboard - send to the server](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.6/iPhone.Load.Clipboard.shortcut)
- [iPhone Download Clipboard - receive the latest item](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.6/iPhone.Download.Clipboard.shortcut)

Open the downloaded files on the iPhone and add them to the Shortcuts app. Edit the
**Get Contents of URL** action and replace the complete example URL:

- **Load Clipboard:** `http://SERVER_IP:5088/clipboard`
- **Download Clipboard:** `http://SERVER_IP:5088/clipboard/latest/raw`

Use the address displayed by Clipboard Bridge in place of `SERVER_IP`. If applicable,
also add the API token. For an isolated account, append
`?user=NAME&password=PASS` to both URLs.

### Add both Shortcuts to Control Center

To run them without opening the Shortcuts app:

1. Open **Control Center** and tap the **Add (+)** button.
2. Tap **Add a Control**, select **Shortcut**, and tap **Choose**.
3. Choose **Load Clipboard**.
4. Add another Shortcut control and choose **Download Clipboard**.

You can now send or receive the latest item from the iPhone's pull-down Control Center.
Apple documents the same procedure in its
[Shortcuts User Guide](https://support.apple.com/guide/shortcuts/apd06a9201d4/ios).

### 5.1 Send (clipboard to server)

This version automatically handles a single item or a list received from the iOS Share
Sheet. Enable **Show in Share Sheet** in the Shortcut details and allow **Any** input.

1. Add **If** and set the condition to **Shortcut Input has any value**.
2. Inside the first branch, add **Set Variable**: name it `Transfer` and set it to
   **Shortcut Input**.
3. In **Otherwise**, add **Get Clipboard**, then **Set Variable** `Transfer` to the
   **Clipboard** result.
4. After **End If**, add **Count** and count the items in `Transfer`.
5. Add another **If**: `Count is greater than 1`.
6. In its first branch, add **Make Archive** with `Transfer` as input and ZIP format.
7. Add **Get Contents of URL**:
   - URL: `http://SERVER_IP:5088/clipboard/bundle`
   - Method: **POST**
   - Request Body: **File**, using the **Archive** result.
8. In **Otherwise**, add **Get Item from List** and choose **First Item** from `Transfer`.
9. Add **Get Type** for the selected item and an **If** action:
   - when the type is **Text**, POST the selected item as a **File** request body to
     `http://SERVER_IP:5088/clipboard`;
   - otherwise, use **Get Details of Files > Name**, URL-encode that name, and POST the
     selected item as a **File** request body to
     `http://SERVER_IP:5088/clipboard?filename=ENCODED_NAME`.
10. Close both **End If** blocks and add **Show Notification**.

The ZIP exists only during transport. `/clipboard/bundle` validates it, ignores Apple
metadata, strips paths and creates one ordered server-history group. Selecting one or
twenty files therefore creates exactly one history row. A normal ZIP sent through
`/clipboard` is never unpacked.

The `filename` parameter is important for formats that iOS does not recognize, such as
`.shortcut`, uncommon archives and application-specific documents. Their MIME type may
only be `application/octet-stream`; the explicit name ensures the server and every
receiving device preserve the original extension. If the URL already contains account
or token parameters, append it with `&filename=ENCODED_NAME` instead of `?filename=...`.

### 5.2 Receive (server to clipboard)

1. Add **Get Contents of URL** with method **GET** and URL:
   `http://SERVER_IP:5088/clipboard/latest/meta`.
2. Add **Get Dictionary Value**, key `type`.
3. Add **If**: the dictionary value **is** `bundle`.
4. In the first branch, add **Get Contents of URL** with method **GET** and URL:
   `http://SERVER_IP:5088/clipboard/latest/raw`.
5. Add **Extract Archive**, then **Copy to Clipboard** using all extracted files.
6. In **Otherwise**, request the same `/clipboard/latest/raw` URL and add
   **Copy to Clipboard** using that response.
7. Close **End If** and add **Show Notification**.

The metadata request contains no file data, so the Shortcut can choose the correct branch
quickly. Text, a photo, one file or a complete file group is then copied automatically.
The extracted group can also be passed to **Save File** when permanent local storage is
preferred.

For an account or token, append the same query parameters to **every URL above**, including
`/clipboard/bundle` and `/clipboard/latest/meta`. Alternatively, use the same
`X-Auth-Token` header in every **Get Contents of URL** action.

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
| iPhone shortcut fails | Verify the URL and method; if you use a token, the header must be present. For universal sending use POST with **File → Clipboard**. |
| A received image isn't on the Windows clipboard | Some apps only accept certain formats; the client copies images as bitmap (works in Office, Paint, chats). |
| Duplicate tray icons | Make sure only one instance of the client is running (close extra ones from Task Manager). |
