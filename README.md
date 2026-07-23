# Clipboard Bridge                    <img width="38" height="38" alt="icon-3" src="https://github.com/user-attachments/assets/dac966a8-3d10-43e7-87e8-161ff5d45b16" />

**English** · [Italiano](README.it.md)

![platform](https://img.shields.io/badge/platform-Windows%20%2B%20iPhone-2563eb)
![modes](https://img.shields.io/badge/modes-Server%20%C2%B7%20Client-6f42c1)
![network](https://img.shields.io/badge/network-local%20only-2ea44f)
![license](https://img.shields.io/badge/license-MIT-555)


Share your clipboard — text, images and **files of any type** — between **Windows and
iPhone** over your local network, using the iOS Shortcuts app. No cloud, no account.
Interface in **English (default)** and Italian.

## ⚡ It works in two distinct modes

![Server mode vs Client mode](docs/modes.png)

Switch anytime from the tray icon (**right-click → Mode**):

| | 🖥️ Server mode | 🔌 Client mode |
|---|---|---|
| **Who is the server** | the **Windows app itself** | a **separate server** (PC, NAS, Raspberry Pi, Docker) |
| **The iPhone connects to** | your PC, directly | the server |
| **Extra setup** | none — just flip the switch | run the server somewhere |
| **Web page** | no (minimal) | yes |
| **Best for** | quick PC ↔ iPhone, zero extra setup | always available, even when your PC is off o even to share clipboard over more PC's |

> 📖 **New here?** Follow the step-by-step [Setup & Usage Guide](GUIDE.md).

## Features
- Exchange **text, images and files** of any type.
- **History** on the server and on the client.
- **Windows client** in the tray: send/receive and global keyboard shortcuts.
- **Web interface** on the server (usable from the iPhone browser too) to paste text and
  upload/download files.
- Integration with **iPhone Shortcuts** via simple HTTP requests.
- **No separate server needed (optional):** the Windows app can be the server itself
  (tray → **Mode → Server**) — the iPhone connects straight to your PC.
- Optional **token** for the API and an optional **password** for the web page.
- Run the server directly or with **Docker**.

<img width="296" height="216" alt="features" src="https://github.com/user-attachments/assets/7d525e31-305c-4c86-bfa7-081aca3fda96" />

<img width="264" height="356" alt="settings" src="https://github.com/user-attachments/assets/9e624278-e712-44a1-9c88-ec5a2e0e4712" />

## Repository layout

| File | Description |
|------|-------------|
| `clipboard_bridge-Server.py` | server (Flask): API, web interface, history |
| `clipboard_bridge_windows.py` | Windows client (tray icon) |
| `Dockerfile`, `docker-compose.yml` | run the server in a container |
| `requirements-server.txt`, `requirements-client.txt` | dependencies |
| `build_client.bat` | build the client into a single `.exe` |
| `icon.ico` | application icon |

> The client executable is not committed: build it with `build_client.bat` (see below) or
> download it from the Releases page, if available.

---

## 1. Server

### Run directly
```bash
pip install -r requirements-server.txt
python clipboard_bridge-Server.py
```
The server listens on all interfaces, port **5088**. Open `http://localhost:5088/` in a
browser for the web interface.

### Docker
```bash
docker compose up -d --build
```
The history is stored in the `./data` folder and survives restarts. Works in any Docker
environment.

For prebuilt multi-architecture images, one-click stores and installation through
ZimaOS, Portainer, Umbrel or Runtipi, see
[Docker and app-store installation](DOCKER.md). Store manifests are kept separately
in [`distribution/clipboard-bridge-store`](distribution/clipboard-bridge-store).

Permanent ZimaOS source:

```text
https://github.com/mattbox03/Clipboard-Bridge-AppStore/archive/refs/heads/main.zip
```

### Options (environment variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `CLIPBOARD_PORT` | `5088` | listening port |
| `CLIPBOARD_TOKEN` | *(empty)* | if set, the API (`/clipboard/*`) needs the `X-Auth-Token` header |
| `CLIPBOARD_PASSWORD` | *(empty)* | if set, the web page requires a login (long-lived per-device session) |
| `CLIPBOARD_ACCOUNTS` | *(empty)* | extra isolated accounts, format `user1:pass1,user2:pass2` (see below) |
| `CLIPBOARD_ACCOUNTS_FILE` | *(empty)* | path to a file with one `user:password` per line (for many accounts) |
| `CLIPBOARD_MAX_HISTORY` | `200` | number of items kept in the history |
| `CLIPBOARD_DATA_DIR` | `./clipboard_data` | data folder |

> For use outside the local network, set a token and use a VPN or a reverse proxy with
> HTTPS. On the local network, allow port 5088 through the firewall.

### Multiple accounts (optional)

The **shared space** is always available. To add extra, **isolated** spaces (each with its
own history), set `CLIPBOARD_ACCOUNTS`:

```bash
CLIPBOARD_ACCOUNTS="alice:secret1,bob:secret2"
```

There is **no limit** on the number of accounts. For many users, instead of a long variable
use an accounts **file** (one `user:password` per line, `#` for comments) and point
`CLIPBOARD_ACCOUNTS_FILE` to it:

```bash
# accounts.txt
alice:secret1
bob:secret2
# ...as many as you want
```
```bash
CLIPBOARD_ACCOUNTS_FILE=/data/accounts.txt python clipboard_bridge-Server.py
```

Pick an account by adding its credentials **at the end of the URL** — handy in a Shortcut or
in the Windows client:

```
http://SERVER_IP:5088/clipboard/latest/raw?user=alice&password=secret1
```

In a browser, open `http://SERVER_IP:5088/` and **log in** (username = account, or leave it
empty for the shared space). The session is remembered per device. The shared space keeps
using `CLIPBOARD_TOKEN` / `CLIPBOARD_PASSWORD` as before.

---

## 2. Windows client

Replace `SERVER_IP` with the address of the machine running the server.

### Executable
Build the client with `build_client.bat` (requires Python). You get
`dist\Clipboard Bridge.exe`, which runs without installing anything.

### From source
```bash
pip install -r requirements-client.txt
python clipboard_bridge_windows.py
```

A tray icon appears (right-click for the menu):
- **Send clipboard -> server** / **Receive latest <- server** (text, images, files).
- **Send a file...** and **Open received folder** (received files go into `ricevuti`).
- **History...**, **Keyboard shortcuts** (default `Ctrl+Alt+C` sends, `Ctrl+Alt+V` receives).
- **Language** (English / Italiano) and **Settings...** (server IP, port, token, account).
  Leave **Account** empty for the shared space, or enter an account name + password to use
  an isolated space.

### Start with Windows
`Win+R` -> `shell:startup`, then put a shortcut to the executable there.

---

## 3. Web interface

Opening the server address in a browser (also from an iPhone) shows a page where you can
paste text, upload and download files, and read the Shortcuts instructions. With a token:
`http://SERVER_IP:5088/?token=YOUR_TOKEN`. Add `?lang=it` for Italian.

---

## 4. iPhone (Shortcuts)

Create shortcuts using the **Get Contents of URL** action. If you use a token, add the
`X-Auth-Token` header.

- **General send** - POST to `http://SERVER_IP:5088/clipboard` (Request body : File, File -> Clipboard).
- **General Recieve** - GET contents of `http://SERVER_IP:5088/clipboard/latest/raw`(Method : GET ; Copy "Contents of URL" to clipboard).
- **Send text** — POST to `http://SERVER_IP:5088/clipboard/text` (JSON body, field `text`).
- **Receive text** — GET `http://SERVER_IP:5088/clipboard/text/raw`, then *Copy to Clipboard*.
- **Send photo/file** — POST to `http://SERVER_IP:5088/clipboard/image` (body: File).
- **Receive image** — GET `http://SERVER_IP:5088/clipboard/image/latest/raw`, then *Save to Album*.

> Using an account? Just append `?user=NAME&password=PASS` to the end of each URL.

---

## 5. Server API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | server status (public) |
| POST | `/clipboard` | save anything (text or binary), type auto-detected |
| POST | `/clipboard/text` | save text (JSON, form or raw body) |
| GET | `/clipboard/text/raw` | latest text as text/plain |
| POST | `/clipboard/image` | save a file/image (base64, multipart or binary) |
| GET | `/clipboard/image/latest/raw` | latest image as binary |
| POST | `/clipboard/file` | save a file (JSON `{filename, data}`) |
| GET | `/clipboard/latest` | latest item of any type, content included |
| GET | `/clipboard/latest/raw` | latest item (any type) as raw content / file |
| GET | `/clipboard/history?limit=N` | history list (metadata) |
| GET/DELETE | `/clipboard/item/<id>` | read or delete an item |
| DELETE | `/clipboard/history` | clear the history |

---

## Building the client executable

```bash
build_client.bat
```
Uses PyInstaller to produce `dist\Clipboard Bridge.exe`. To change the icon, replace
`icon.ico` with your own and run the script again.

## License

Released under the [MIT](LICENSE) license.
