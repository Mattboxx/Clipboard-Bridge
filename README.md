# Clipboard Bridge - Windows and iPhone Clipboard Sync <img width="38" height="38" alt="Clipboard Bridge application icon" src="https://github.com/user-attachments/assets/dac966a8-3d10-43e7-87e8-161ff5d45b16" />

**English** · [Italiano](README.it.md)

[Website](https://mattbox03.github.io/Clipboard-Bridge/) ·
[Windows downloads](https://github.com/mattbox03/Clipboard-Bridge/releases) ·
[Server App Store](https://github.com/mattbox03/Clipboard-Bridge-AppStore) ·
[Code signing policy](CODE_SIGNING.md)

**Windows 2.0.2:** [Installer, no administrator privileges](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.2/Clipboard.Bridge_windows_client_and_server_setup_x64_V2.0.2.exe) ·
[Portable, no installation or administrator privileges](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.2/Clipboard.Bridge.Portable.Windows.x64.V2.0.2.exe)

The complete `2.0.2` release also contains both ready-made iPhone Shortcuts, the Python
server, Docker/Compose files and the server requirements.

> **Windows security:** release 2.0.2 is currently unsigned and can be blocked by
> Windows 11 Smart App Control. The project is preparing trusted Authenticode signing;
> see the [code signing policy](CODE_SIGNING.md). A self-signed certificate would not
> make a public download trusted.

> **Auto-sync on Windows:** this warning applies to both the installer and portable
> versions. Windows may prevent Clipboard Bridge from detecting clipboard changes made by
> applications running as administrator. If auto-sync does not work, right-click Clipboard
> Bridge and choose **Run as administrator**.

![platform](https://img.shields.io/badge/platform-Windows%20%2B%20iPhone-2563eb)
![modes](https://img.shields.io/badge/modes-Server%20%C2%B7%20Client-6f42c1)
![network](https://img.shields.io/badge/network-local%20only-2ea44f)
![license](https://img.shields.io/badge/license-MIT-555)


Share your clipboard — text, images and **files of any type** — between **Windows and
iPhone** over your local network, using the iOS Shortcuts app. No cloud, no account.
Interface in **English (default)** and Italian.

## ⚡ It works in two distinct modes

![Server mode vs Client mode](docs/modes.png)

Switch anytime from **Settings → General**:

| | 🖥️ Server mode | 🔌 Client mode |
|---|---|---|
| **Who is the server** | the **Windows app itself** | a **separate server** (PC, NAS, Raspberry Pi, Docker) |
| **The iPhone connects to** | your PC, directly | the server |
| **Extra setup** | none — just flip the switch | run the server somewhere |
| **Web page** | no (minimal) | yes |
| **Best for** | quick PC ↔ iPhone, zero extra setup | always available, even when your PC is off o even to share clipboard over more PC's |

> 📖 **New here?** Follow the step-by-step [Setup & Usage Guide](GUIDE.md).

**Clipboard Bridge is an open-source, self-hosted clipboard synchronization and file
transfer tool for Windows and iPhone.** It can run entirely on a Windows PC or connect
multiple devices to a private Flask and Docker server. It transfers the latest clipboard
item over the local network without relying on iCloud, Microsoft Cloud Clipboard or an
external cloud service.

## Features
- Exchange **text, images and files** of any type.
- **History** on the server and on the client.
- **Windows client** in the tray: send/receive and global keyboard shortcuts.
- **Automatic incoming files:** new PDFs and other files are downloaded while the client
  is running; click the Windows notification to reveal the file.
- **Web interface** on the server (usable from the iPhone browser too) to paste text and
  upload/download files.
- Integration with **iPhone Shortcuts** via simple HTTP requests.
- **No separate server needed (optional):** the Windows app can be the server itself
  (**Settings → General → Server**) — the iPhone connects straight to your PC.
- Optional **token** for the API and an optional **password** for the web page.
- Run the server directly or with **Docker**.

<img width="296" height="216" alt="features" src="https://github.com/user-attachments/assets/7d525e31-305c-4c86-bfa7-081aca3fda96" />

<img width="264" height="356" alt="settings" src="https://github.com/user-attachments/assets/9e624278-e712-44a1-9c88-ec5a2e0e4712" />

## Common use cases

- **Sync the clipboard between Windows and iPhone** using two iOS Shortcuts.
- **Send photos and files from an iPhone to a Windows PC** over Wi-Fi.
- **Copy text from Windows and paste it on iOS**, or receive iPhone clipboard content
  on Windows.
- Run a **self-hosted clipboard server** on a NAS, Raspberry Pi, home server or Docker
  host.
- Use **Windows as the clipboard server** when no NAS or separate server is available.
- Share one server between multiple people through **isolated clipboard accounts**.
- Keep clipboard and file transfers inside a **private local network**.

## Repository layout

| File | Description |
|------|-------------|
| `clipboard_bridge-Server.py` | server (Flask): API, web interface, history |
| `clipboard_bridge_windows.py` | Windows client (tray icon) |
| `Dockerfile`, `docker-compose.yml` | run the server in a container |
| `requirements-server.txt`, `requirements-client.txt` | dependencies |
| `build_client.bat` | build the client into a single `.exe` |
| `build_windows_release.bat` | build both the portable EXE and Windows installer |
| `Clipboard_Bridge_setup.iss` | universal Inno Setup installer definition |
| `icon.ico` | application icon |

> Download the tested installer or portable executable from Releases. The tracked
> `dist\Clipboard Bridge.exe` can also be rebuilt locally with the scripts below.

---

## 1. Server

### Install from an app store

The server is also distributed through the separate
**[Clipboard Bridge App Store](https://github.com/mattbox03/Clipboard-Bridge-AppStore)**.
Its README contains detailed installation and update instructions for:

- **ZimaOS** one-click installation
- **Portainer** App Templates
- **Umbrel** Community App Store
- **Runtipi** custom app
- **Docker Compose**, Docker Desktop and Dockge

Open the **[App Store installation guide](https://github.com/mattbox03/Clipboard-Bridge-AppStore#readme)**
and follow the section for your platform. The permanent ZimaOS source is:

```text
https://github.com/mattbox03/Clipboard-Bridge-AppStore/archive/refs/heads/main.zip
```

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

Stable server image: `ghcr.io/mattbox03/clipboard-bridge-server:1.0.1`.

For container details, backups and image tags, see
[Docker and app-store installation](DOCKER.md).

### Options (environment variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `CLIPBOARD_PORT` | `5088` | listening port |
| `CLIPBOARD_TOKEN` | *(empty)* | if set, the API (`/clipboard/*`) needs the `X-Auth-Token` header |
| `CLIPBOARD_PASSWORD` | *(empty)* | if set, the web page requires a login (long-lived per-device session) |
| `CLIPBOARD_ACCOUNTS` | *(empty)* | extra isolated accounts, format `user1:pass1,user2:pass2` (see below) |
| `CLIPBOARD_ACCOUNTS_FILE` | *(empty)* | path to a file with one `user:password` per line (for many accounts) |
| `CLIPBOARD_MAX_HISTORY` | `200` | number of items kept in the history |
| `CLIPBOARD_MAX_UPLOAD_MB` | `64` | maximum size of one request or uploaded file in MB |
| `CLIPBOARD_DATA_DIR` | `./clipboard_data` | data folder |

> For use outside the local network, set a token and use a VPN or a reverse proxy with
> HTTPS. [Tailscale](https://tailscale.com/) is one simple VPN option: install it on the
> iPhone and on the PC/server, then use the server's Tailscale IP in the Shortcuts
> (`http://100.x.y.z:5088`). You do not need to expose port 5088 on the router. On the
> local network, allow port 5088 through the host firewall. This also works when the
> Windows app runs in **Server mode**: use that Windows PC's Tailscale IP and the port
> configured in the app.

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

These URL credentials remain supported for iPhone Shortcuts. As an optional alternative,
API clients may send `X-Clipboard-User` and `X-Clipboard-Password` headers instead.

In a browser, open `http://SERVER_IP:5088/` and **log in** (username = account, or leave it
empty for the shared space). The session is remembered per device. The shared space keeps
using `CLIPBOARD_TOKEN` / `CLIPBOARD_PASSWORD` as before.

---

## 2. Windows client

Replace `SERVER_IP` with the address of the machine running the server.

### Executable
Download the ready-made installer/portable build from Releases, or build only the portable
client with `build_client.bat` (requires Python). You get `dist\Clipboard Bridge.exe`,
which runs without installing anything.

### From source
```bash
pip install -r requirements-client.txt
python clipboard_bridge_windows.py
```

A tray icon appears (right-click for the menu):
- **Send clipboard -> server** / **Receive latest <- server** (text, images, files).
- **Send a file...** and **Open received folder**. New remote files are downloaded
  automatically to `%USERPROFILE%\Downloads\Clipboard Bridge`; clicking their notification
  opens File Explorer and selects the received file. Received files are also placed on the
  Windows clipboard, ready to paste into File Explorer or another compatible application.
- **History...** and **Language** remain immediately available in the tray.
- **Settings...** contains operating mode, interface language, local-history limit,
  server address, ports, token, account, automation and configurable hotkeys. Leave
  **Account** empty for the shared space, or enter an account name + password to use an
  isolated space. Default hotkeys are `Ctrl+Alt+C` to send and `Ctrl+Alt+V` to receive.
- The tray shows one compact green/red connection indicator. Settings provide the full
  status and **Check connection now** after changing the address or credentials.

The installed application never writes runtime data inside `Program Files`. Configuration,
local history, embedded Server-mode data and crash logs are stored in
`%LOCALAPPDATA%\Clipboard Bridge`. Existing data found beside an older executable is copied
automatically on first run. Version 2.0.2 also searches old `Program Files` installations
and recovers settings when 2.0.1 previously created an empty default configuration.

### Start with Windows
`Win+R` -> `shell:startup`, then put a shortcut to the executable there.

---

## 3. Web interface

Opening the server address in a browser (also from an iPhone) shows a page where you can
paste text, upload and download files, and read the Shortcuts instructions. With a token:
`http://SERVER_IP:5088/?token=YOUR_TOKEN`. Add `?lang=it` for Italian.

---

## 4. iPhone (Shortcuts)

The ready-made Shortcuts are included as assets in the
[Clipboard Bridge 2.0.2 release](https://github.com/mattbox03/Clipboard-Bridge/releases/tag/2.0.2):

- **[Download Load Clipboard](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.2/Load.Clipboard.shortcut)** -
  sends the current iPhone clipboard to Clipboard Bridge.
- **[Download Download Clipboard](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.2/Download.Clipboard.shortcut)** -
  receives the latest item from Clipboard Bridge.

Open each `.shortcut` file on the iPhone and replace the placeholder server address with
the address shown by the Windows app or your external server. Also add your token or
account credentials when enabled.

### Add the Shortcuts to Control Center

For one-swipe access without opening the Shortcuts app:

1. Open **Control Center** on the iPhone and tap the **Add (+)** button.
2. Tap **Add a Control**, select **Shortcut**, then tap **Choose**.
3. Select **Load Clipboard**. Repeat the steps and select **Download Clipboard** for a
   second control.

The two controls can now send or receive the latest clipboard item directly from Control
Center. See [Apple's Control Center guide](https://support.apple.com/guide/shortcuts/apd06a9201d4/ios).

### Create them manually

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

## Building the Windows packages

To build only the portable executable:

```bat
build_client.bat
```

To create both universal GitHub release assets:

```bat
build_windows_release.bat 2.0.2
```

The script uses PyInstaller and Inno Setup, without personal paths or configuration files.
It produces:

```text
Output\Clipboard.Bridge.Portable.Windows.x64.V2.0.2.exe
Output\Clipboard.Bridge_windows_client_and_server_setup_x64_V2.0.2.exe
Output\Clipboard.Bridge.Release.V2.0.2\
```

The installer is per-user: it installs under `%LOCALAPPDATA%\Programs\Clipboard Bridge`
and does not require administrator privileges. Application settings and received files
remain in the current user's profile. The release folder contains the two Windows builds,
both iPhone Shortcuts, the Python server and all Docker/Compose files needed to deploy it.

Install missing build tools with:

```powershell
winget install --id Python.Python.3.12 --exact
winget install --id JRSoftware.InnoSetup --exact
```

## Frequently asked questions

### Can I share the clipboard between Windows and iPhone without iCloud?

Yes. Clipboard Bridge sends text, photos and files through your local network. The
iPhone uses the Shortcuts app and Windows uses the tray client.

### Does it require a separate server?

No. In **Server mode**, the Windows application accepts connections directly from the
iPhone. In **Client mode**, it connects to an always-on Clipboard Bridge server running
on Docker, a NAS, Raspberry Pi or another computer.

### Can it transfer photos and arbitrary files?

Yes. The unified endpoints and iPhone Shortcuts handle text, images and files according
to the latest item saved on the server.

### Is Clipboard Bridge a cloud clipboard service?

No. It is self-hosted and designed primarily for local networks. Remote access should
be protected with HTTPS through a VPN or reverse proxy.

### Which self-hosting platforms are supported?

The server supports Docker Compose and includes installation instructions for ZimaOS,
Portainer, Umbrel, Runtipi, Docker Desktop and Dockge in the
[Clipboard Bridge App Store](https://github.com/mattbox03/Clipboard-Bridge-AppStore).

### Does it support multiple users?

Yes. The shared clipboard remains available, while an arbitrary practical number of
password-protected accounts can have separate histories and files.

## License

Released under the [MIT](LICENSE) license.
