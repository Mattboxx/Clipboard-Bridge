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
Download the installer or portable EXE from the GitHub Release. Choose **x64** for
Intel/AMD PCs, or the native **ARM64** downloads for Windows 11 ARM devices, such as
Snapdragon PCs and ARM-based Surface models. To identify your device, open **Settings >
System > About > System type**. The ARM64 version has the same functions, including
image and PDF previews.

Both architectures share settings and history. Quit Clipboard Bridge before switching
architectures, then install the other package normally; do not delete your data folder.

To rebuild x64 packages locally, run `scripts\windows\build_release.bat 2.0.18` (requires x64
Python, PyInstaller and Inno Setup). Native ARM64 builds use the **Build Windows ARM64**
GitHub Actions workflow; see [CONTRIBUTING.md](CONTRIBUTING.md#windows-release-builds).
No personal configuration is embedded in any package.
The installer uses the current user's LocalAppData folder and does not require
administrator privileges.

### Windows updates

From 2.0.18, open **Settings > Updates**:

1. **Check now** looks for a newer stable Windows release in the official GitHub
   repository. It never installs just because you pressed Check.
2. **Download and install** shows progress, lets you cancel the download and asks
   before restarting. Save any Settings changes first.
3. Leave **Check GitHub for updates automatically** enabled for a background check
   about 30 seconds after launch (when due) and at most once per day after success.
   Offline failures retry later; they do not block clipboard sharing.
4. To install without the confirmation each time, enable **Download and install
   updates automatically** and click **Save**. This is off by default. Settings
   windows defer automatic installation; close them when you are ready. The client
   waits for its active transfers, then briefly stops sharing while restarting.

The updater retains the running executable's architecture and package type.
Portable updates replace the same EXE in the same writable folder; the installer
updates the current per-user installation. Configuration, history and received files
stay in their existing user folders. Read-only locations must be updated manually.
Run source checkouts with Git/pip instead; the updater installs only frozen EXEs.
Clients older than 2.0.18 need one manual upgrade before these controls exist.

Downloads use HTTPS and exact official asset names. Size, GitHub SHA-256, embedded
version and executable architecture are checked before replacement. Checks contact
GitHub without sending clipboard contents or server/account credentials. These
checks are not trusted publisher signing: packages are still unsigned, and Windows
may require approval or block them. No Windows protection is disabled. Automatic
installation cannot promise to bypass that decision. A failed application/start
attempt restores the previous EXE when possible, but cannot undo every external
installer/Windows failure; use the GitHub installer if recovery fails. A failed
version is not retried automatically for 24 hours; manual retry remains available.

> **Windows 11 security:** version 2.0.18 is currently unsigned, so Smart App Control can
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
   In **Settings > Shortcuts**, set separate shortcuts for Send, Receive and
   **History** (default **Ctrl+Alt+H**). Press once to open History, again to close
   it and again to reopen it. Tray clicks still open or focus the window. These
   actions never upload the clipboard. Saved changes take
   effect immediately. Choose different, valid key combinations for each action.
   Use **Set keys...** to record the combination instead of typing its name:
   press and release the keys, then click **Save**. Escape cancels recording.
   Global shortcuts are paused during recording to avoid sending your clipboard.
   Windows checks that the combination is available; occupied shortcuts leave your
   previous settings intact. F12 is reserved by Windows and cannot be selected.

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
  Left-clicking the tray icon opens this window; it does not send the clipboard.

In Windows 2.0.18, History also offers a search field, type filter
and previous/next server pages. Search matches previews and filenames, including all
files in a group, not full document contents. The standalone server web page has the
same controls. Changing a filter restarts from the first page; Clear on the web page
still clears the entire selected account's history, not just the search results.
History uses one compact list: choose **Server** or **This PC**, then double-click an
item or press **Copy**. Local items can also be sent with **Send to server**.
The **Preview** checkbox opens or closes the optional preview pane. Selected images
are shown as thumbnails, with proportions and camera orientation preserved. PDFs
show their first page and page count, without requiring an installed PDF reader.
This also works for local files and the first supported member in a file group. Loading runs
in the background and does not copy anything or save extra files. Missing, unsupported
or unusually large files, and password-protected PDFs, show a preview-unavailable
message; transfers are unchanged.
Each server page
contains up to 100 items; **Previous** and **Next** navigate between pages.
Settings use sidebar navigation. Choose **General → Appearance → Light / Dark**;
the preview updates open windows immediately and Cancel restores your saved appearance.
Dark is the default. Settings sections scroll when needed.
The optional Ko-fi link is at the bottom of Settings, with a localized explanation
and thank-you. It opens only when clicked; no reminder or popup is shown automatically.
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

### Mac compatibility

The same HTTP send/receive workflow can be built in **Shortcuts on Mac**: use Get
Clipboard, Get Contents of URL and Copy to Clipboard with the URLs below. You can
run these actions from Shortcuts or assign a keyboard shortcut, as explained in
[Apple's Shortcuts for Mac guide](https://support.apple.com/guide/shortcuts-mac/welcome/mac).
No native Mac app or continuous macOS clipboard synchronization is included.
The distributed iPhone `.shortcut` files are signed Apple containers and have
not been tested on a physical Mac. If importing them fails, build the same actions
manually using this guide. iPhone Control Center instructions apply only to iOS.

You only need **two** shortcuts. They make no distinction between text and photos: they
always send, or fetch, the **most recent** item. Both use the built-in **Get Contents of
URL** action. If your server uses a token, add a **Header** `X-Auth-Token` = `YOUR_TOKEN`
to each shortcut.

### Download the ready-made Shortcuts

Both prepared iPhone Shortcuts are included in the
[Clipboard Bridge 2.0.18 release](https://github.com/Mattboxx/Clipboard-Bridge/releases/tag/2.0.18):

- [iPhone Load Clipboard - send to the server](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.18/iPhone.Load.Clipboard.shortcut)
- [iPhone Download Clipboard - receive the latest item](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.18/iPhone.Download.Clipboard.shortcut)

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

Copied text is stored and received as **plain Unicode text**. Server 1.0.9 and
Windows Server mode 2.0.18 remove RTF formatting without removing emoji or accents.
Documents sent as files, including `.rtf`, keep their original bytes.

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
9. Add **Get Type** for the selected item and nested **If** actions:
   - for a **URL**, insert the selected URL into a **Text** action, keeping its
     variable type **URL**, not Article or Contents of URL;
   - for a **Safari Web Page**, use **Get Details of Safari Web Page > URL**, then
     insert that URL into a **Text** action. Do not extract the page body;
   - for **Text** or **Rich Text**, use **Get Text from Input** on the selected item;
   - send the resulting text to `http://SERVER_IP:5088/clipboard` with method
     **POST**, Request Body **JSON**, adding a field named `text` of type **Text**.
     Its value must be the text result from the appropriate branch, not the original
     URL/web-page variable. Let Shortcuts encode the JSON; do not construct JSON by
     concatenating strings. Do not add a filename or a File-body header here;
   - otherwise, use **Get Details of Files > Name**, URL-encode that name, and POST the
     selected item as a **File** request body to
     `http://SERVER_IP:5088/clipboard?filename=ENCODED_NAME`.
10. Close the **If** blocks and add **Show Notification**.

Keep the ZIP branch for multiple files. For several links, combine the URL strings
with line breaks and send them in the same JSON `text` field instead of archiving
URL objects. Files remain files, even when an HTML or text document contains links.

### Sharing a link sends HTML instead of its address

If a Reddit or other website link arrives as `<!DOCTYPE html>...`, page contents
were fetched somewhere in the sending workflow, or the source app supplied HTML.
Clipboard Bridge stores the received content; its upload endpoints do not visit
URLs or recover an original link from a downloaded page.
[Apple documents automatic type conversion in Shortcuts](https://support.apple.com/guide/shortcuts/the-content-graph-engine-apd4618db957/ios).

In **Load Clipboard**, keep the URL in **Get Contents of URL** fixed to your
Clipboard Bridge host, not the shared Reddit address. Use the URL/Safari branches
above and send **JSON > text (Text) > text result**, not **File > original input**.
Do not add **Get Contents of Web Page** or an extra GET to the shared address.
Account/token query parameters on the host URL stay unchanged.

To diagnose your installed variant, temporarily put **Show Result** immediately
before the POST and select the outgoing text value. It should show only the link
(or intended copied text), never HTML or an article. If it already shows HTML,
inspect the preceding actions or the source app's Share Sheet output. As a quick
fallback, use the source app's **Copy Link**, then run Load Clipboard on that copied
text. Remove the temporary preview after testing; it can display private content.
The signed downloads have not been edited or re-signed by this documentation change;
the change must be applied and tested on the Apple device.

### File names and grouped transfers

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

The existing default is 3650 days. Set `CLIPBOARD_SESSION_DAYS=90` or `365` for a
shorter remembered login; Compose exposes the same setting as `SESSION_DAYS`.
This setting never adds a login step to Apple Shortcuts.

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

Windows and Android retain the compatible account URL format. Android skips its
optional duplicate headers when Unicode or whitespace-sensitive values would make
them invalid. Plain HTTP does not encrypt either transport. **Your existing Apple
URLs remain valid:** no pairing, interactive login, refresh token or required header
is introduced. The Windows app currently uses HTTP; use LAN/VPN with it rather than
assuming it can connect directly to an HTTPS-only reverse proxy.

> Plain HTTP does not encrypt clipboard contents or credentials. **Away from home or on
> untrusted Wi-Fi, we recommend [Tailscale](https://tailscale.com/)**: install it on the iPhone and
> server, then replace `SERVER_IP` in both Shortcuts with the server's Tailscale IP
> (usually `100.x.y.z`). This includes the Windows app's **Server mode**: install Tailscale
> on that PC and use its Tailscale IP plus the port configured in Clipboard Bridge. No
> router port forwarding is required.

---

## 8. Troubleshooting

### Local network, VPN and subnet routing

**Every device must be able to reach the clipboard host.** On a trusted local
network, use its LAN address. **Away from home or on untrusted Wi-Fi, we recommend
[Tailscale](https://tailscale.com/).** It is optional: another private VPN can work
too, and a trusted LAN needs no VPN. Both Docker/Python hosting and Windows Server
mode support this approach. Keep the selected host running.

The simplest remote setup installs the VPN on the host and each client, then uses
the host's VPN address in Windows, Android and both Apple Shortcuts.

Join the same private Tailscale network on those devices; follow the
[official quickstart](https://tailscale.com/docs/how-to/quickstart). For Docker,
the VPN must reach the machine hosting the container's published port. For
Windows Server mode, use that PC's Tailscale address and configured clipboard port.
You do not need to change the Shortcut actions, account URLs or clipboard format.

**On an untrusted network, use the VPN address, not a direct LAN URL.** Keep port
`5088` blocked on public/untrusted interfaces using the host firewall. Turning on
a VPN does not automatically restrict a server that also listens on those interfaces.
With subnet routing, the route from the gateway to the destination may still be
plain HTTP: keep that LAN trusted, or use appropriate transport protection.

Tailscale normally routes traffic to your private devices, not all internet
browsing. An [exit node](https://tailscale.com/docs/features/exit-nodes) is a separate,
optional choice for routing general internet traffic; it is not required for
Clipboard Bridge transfers between Tailscale-connected devices.

#### Keep the same LAN address at home and away

If you have a home server or NAS, it can act as a **subnet router**: a gateway
from your VPN into the home LAN. This lets the same local clipboard URL work
remotely without changing every app and Shortcut. It does not change the server's IP.

Example only: if the server is `192.168.50.10` on `192.168.50.0/24`, keep
`http://192.168.50.10:5088` in each client, at home and away.

1. Reserve the server's LAN IP in your home router, so DHCP does not change it.
2. Install Tailscale on the always-on gateway; follow its platform-specific
   [subnet-router setup](https://tailscale.com/docs/features/subnet-routers/how-to/setup).
   Linux also requires IP forwarding. Configure this on the NAS/host or a dedicated
   router, not by changing the Clipboard Bridge container.
3. Advertise the actual home subnet, approve its route in Tailscale and allow the
   intended clients to access the server port. Route approval and access rules
   are separate requirements.
4. Connect the remote phone/PC to the same private VPN and verify that it uses the
   subnet route. With Tailscale, Windows, Android, iOS and macOS normally accept
   approved routes automatically; Linux clients may need route acceptance enabled.
5. Test the same server URL from a phone with home Wi-Fi disabled, using mobile
   data and the VPN. Keep the gateway and clipboard host online.

**An exit node is not a substitute for a subnet router.** If the remote Wi-Fi
uses an overlapping LAN range, routing can conflict; use the host's VPN address
or adjust the LAN plan instead. Do not forward port `5088` to the public internet.
URL credentials remain plain text, and a VPN does not make every local HTTP hop
encrypted; use a trusted LAN or HTTPS where needed.

Official reference: [Tailscale subnet routers](https://tailscale.com/docs/features/subnet-routers).

### Common problems

| Problem | Check |
|---------|-------|
| The web page won't open | Is the server running? Right `SERVER_IP`? Same network? Port 5088 allowed in the firewall? |
| `401 unauthorized` | The token is missing or wrong (`X-Auth-Token` / Settings → Token). |
| iPhone shortcut fails | Verify the host URL and method. Only if a token is configured, include it in the URL or `X-Auth-Token` header. Send text/links as **JSON > text (Text)**; reserve **File** for actual files. See the send recipe above. |
| A received image isn't on the Windows clipboard | Some apps only accept certain formats; the client copies images as bitmap (works in Office, Paint, chats). |
| Duplicate tray icons | Make sure only one instance of the client is running (close extra ones from Task Manager). |
| `503 history_unavailable` in the candidate update | Stop the host and follow [storage recovery](DOCKER.md#history-storage-errors). Do not delete the index or reset configuration to hide the error. |
