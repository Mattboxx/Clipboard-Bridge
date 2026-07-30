# Clipboard Bridge

## One clipboard for Windows, Android and iPhone

**English** | [Italiano](README.it.md)

[Website](https://mattbox03.github.io/Clipboard-Bridge/) |
[Downloads](https://github.com/mattbox03/Clipboard-Bridge/releases/tag/2.0.4) |
[Server App Store](https://github.com/mattbox03/Clipboard-Bridge-AppStore) |
[Setup guide](GUIDE.md)

[![Windows](https://img.shields.io/badge/Windows-client%20%2B%20server-2563eb)](#windows)
[![Android](https://img.shields.io/badge/Android-native%20app-16805b)](#android)
[![iOS](https://img.shields.io/badge/iPhone-Shortcuts-111827)](#iphone-and-ipad)
[![Docker](https://img.shields.io/badge/server-Docker%20%2B%20Python-0ea5e9)](#standalone-server)
[![License](https://img.shields.io/badge/license-MIT-555)](LICENSE)
[![Validate](https://github.com/mattbox03/Clipboard-Bridge/actions/workflows/validate.yml/badge.svg)](https://github.com/mattbox03/Clipboard-Bridge/actions/workflows/validate.yml)

Clipboard Bridge moves the **latest text, image or file** between Windows, Android and
iPhone through a private server. It works on a local network, does not require a cloud
account, and keeps every device on the same server history.

Use the Windows app as the server for the simplest setup, or run the standalone
Python/Docker server on a NAS, Raspberry Pi, home server or any Docker host.

## Download

| Platform | Download | What it includes |
|---|---|---|
| **Android 10+** | [Android APK 1.0.0-beta.7](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Clipboard.Bridge.Android.universal.V1.0.0-beta.7.apk) | Native app, universal Share target, server history and Quick Settings tiles |
| **Windows installer** | [Clipboard Bridge Windows 2.0.4 installer](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Clipboard.Bridge_windows_client_and_server_setup_x64_V2.0.4.exe) | Per-user installation; no administrator account required |
| **Windows portable** | [Clipboard Bridge 2.0.4 portable](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Clipboard.Bridge.Portable.Windows.x64.V2.0.4.exe) | One executable, no installation |
| **iPhone Send Shortcut** | [Load Clipboard](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Load.Clipboard.shortcut) | Sends the current iOS clipboard |
| **iPhone Receive Shortcut** | [Download Clipboard](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Download.Clipboard.shortcut) | Receives the latest server item |
| **Server bundle** | [Source and server ZIP](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Clipboard.Bridge.Source.and.Server.V2.0.4.zip) | Python server, Docker files, documentation and tests |

The Android app is currently a public beta. APK and Windows checksums are included in
the release assets.

> **Windows download warning:** the current Windows executables are not yet signed with
> a public Authenticode certificate. Defender or Smart App Control can therefore show a
> warning. See [CODE_SIGNING.md](CODE_SIGNING.md).

## How it works

```text
Windows app  ─┐
Android app  ─┼── HTTP on your private network ── Clipboard Bridge server
iOS Shortcut ─┘                                  ├─ latest item
Web browser  ────────────────────────────────────└─ shared history
```

The server has one ordered history for each clipboard space. **Text, images and files
have exactly the same priority:** the latest request is always the latest item.

Every device must use the same:

- server address and port;
- shared space or account;
- token, username and password when authentication is enabled.

The Android history is a live view of `GET /clipboard/history`. It is not stored as a
separate Android history.

## Choose a server mode

Clipboard Bridge supports two distinct setups.

| | **Windows Server mode** | **Standalone server** |
|---|---|---|
| Server runs on | The Windows app | Docker/Python host |
| Extra computer required | No | Yes, or an always-on NAS/home server |
| Web interface | No | Yes |
| Android support | Yes | Yes |
| iPhone Shortcuts | Yes | Yes |
| Windows client | The same app | One or more Windows clients |
| Best for | Fast setup and direct phone-to-PC use | Multiple users and an always-on service |

![Windows Server mode and standalone server mode](docs/modes.png)

### Fastest setup: use Windows as the server

1. Install or open Clipboard Bridge on Windows.
2. Open **Settings > General** and select **Server mode**.
3. Keep port `5088`, unless it is already used.
4. Copy the address displayed by the Windows app, for example
   `http://192.168.1.20:5088`.
5. Allow Clipboard Bridge through Windows Firewall when requested.
6. Enter the same address in Android and in both iPhone Shortcuts.

No Docker container or separate web server is required.

### Always-on setup: use Docker or Python

1. Start the standalone server on a NAS, Raspberry Pi, PC or Docker host.
2. Open `http://SERVER_IP:5088/` to verify the web interface.
3. Put the Windows app in **Client mode**.
4. Configure Android and iPhone with the same server address.

## Android

The native Android client supports Android 10 and later.

### Features

- Send and receive Unicode text.
- Send photos, PDFs, archives and arbitrary files.
- Save received files in `Downloads/Clipboard Bridge`.
- Put received text or file URIs into the Android clipboard.
- Live server history, refreshed every five seconds while the app is visible.
- Restore any item directly from server history.
- Android Share menu target for text, images and files.
- **Send clipboard** and **Receive clipboard** Quick Settings tiles.
- Optional foreground monitoring for new server items.
- Separate notification settings for incoming text, incoming files and sent items.
- Shared token and isolated account authentication.
- English and Italian interface.

### Install the APK

1. Download the [Android APK](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Clipboard.Bridge.Android.universal.V1.0.0-beta.7.apk).
2. Open the downloaded file on the Android device.
3. If requested, allow the browser or file manager to install apps from that source.
4. Choose **Install** or **Update**.
5. Open Clipboard Bridge and allow notifications if you want automatic monitoring.

Updates signed by this project keep the existing Android configuration.

### Configure Android

1. Open the gear button.
2. Enter only the server base address, for example:

   ```text
   http://192.168.1.20:5088
   ```

3. Choose **Shared space** when using the general clipboard.
4. Enter the API token only when the server uses `CLIPBOARD_TOKEN`.
5. Choose **Account** only when that username exists in `CLIPBOARD_ACCOUNTS`.
6. Enter the account username and password.
7. Run **Test connection**, then save.

For account mode, the status strip must show **Connected - @USERNAME**. Android appends
`user` and `password` to every request URL, so it loads that account's isolated
clipboard rather than the shared space. The **Server history** section then displays
the same items returned by:

```text
http://SERVER_IP:5088/clipboard/history?limit=200&user=USERNAME&password=PASSWORD
```

If Android and the web page show different histories, check that both are using the
same shared space or the same account.

### Use the Android app

- **Send clipboard:** uploads the current Android clipboard.
- **Receive latest:** downloads the newest server item and places it in the clipboard.
- **Send file:** opens Android's file picker.
- **History item:** downloads that exact server item.
- **Share to Clipboard Bridge:** appears in Android's Share menu for text, images,
  documents and arbitrary file types. One or several selected files are uploaded
  directly without leaving the main Clipboard Bridge screen open.

### Add the Quick Settings controls

1. Pull down Android Quick Settings twice.
2. Tap **Edit** or the pencil button.
3. Find **Send clipboard** and **Receive clipboard**.
4. Drag both into the active controls.

The controls use a transparent helper because Android requires a focused activity for
reliable clipboard access. Clipboard Bridge immediately returns to the previous screen;
the main app is not opened.

### Android automatic synchronization

Android 10 and later prevent ordinary background applications from continuously reading
the clipboard. Clipboard Bridge therefore uses these supported workflows:

- incoming monitoring uses an optional foreground service and notification;
- **Receive clipboard** is always available from Quick Settings;
- outgoing auto-send works while Clipboard Bridge is visible;
- the Share menu and **Send clipboard** tile work from other applications.

Some Android manufacturers apply additional battery restrictions. If monitoring stops,
exclude Clipboard Bridge from battery optimization and keep its foreground notification
enabled.

See [android/README.md](android/README.md) for build instructions and technical details.

## Windows

The Windows client runs from the notification area.

### Main features

- Client mode for an external server.
- Server mode with a built-in HTTP server.
- Manual send and receive.
- Configurable global keyboard shortcuts.
- Automatic clipboard synchronization.
- Local clipboard history.
- Automatic download of incoming files.
- Clickable file notifications.
- Configurable text, image and file notifications.
- Shared token and account authentication.
- Single-instance protection.
- English and Italian interface.

### Windows local history versus server history

The Windows app can record a private local history. This is different from server
history:

- **local history** contains clipboard events observed on that Windows PC;
- **server history** contains items actually uploaded to the selected server;
- Android, iPhone and the web interface can only see server history.

Enable **Automatic synchronization** or use **Send clipboard** to publish Windows items
to the server.

> Clipboard changes made by applications running as administrator may be hidden from a
> normal Windows process. If Windows auto-sync misses those changes, run Clipboard Bridge
> as administrator too.

## iPhone and iPad

iOS uses two universal Shortcuts. The same Shortcut handles text, photos and files.

### Send the current clipboard

Install [Load Clipboard](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Load.Clipboard.shortcut)
and set its request URL to:

```text
http://SERVER_IP:5088/clipboard
```

### Receive the latest item

Install [Download Clipboard](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Download.Clipboard.shortcut)
and set its URL to:

```text
http://SERVER_IP:5088/clipboard/latest/raw
```

Add both Shortcuts to the iPhone Control Center for one-swipe access:

1. Open Control Center customization.
2. Add a **Shortcut** control.
3. Select **Load Clipboard**.
4. Add a second control and select **Download Clipboard**.

For an isolated account, append the encoded username and password:

```text
http://SERVER_IP:5088/clipboard?user=alice&password=secret
http://SERVER_IP:5088/clipboard/latest/raw?user=alice&password=secret
```

For the shared API token:

```text
http://SERVER_IP:5088/clipboard?token=YOUR_TOKEN
http://SERVER_IP:5088/clipboard/latest/raw?token=YOUR_TOKEN
```

The [complete setup guide](GUIDE.md) includes detailed Shortcut actions and file/photo
behavior.

## Standalone server

### Docker Compose

```bash
git clone https://github.com/mattbox03/Clipboard-Bridge.git
cd Clipboard-Bridge
docker compose up -d --build
```

Open `http://localhost:5088/`. Persistent data is stored in `./data`.

### Python

```bash
pip install -r requirements-server.txt
python clipboard_bridge-Server.py
```

### App stores

The separate [Clipboard Bridge App Store](https://github.com/mattbox03/Clipboard-Bridge-AppStore)
provides installation instructions for ZimaOS, Portainer, Umbrel, Runtipi, Dockge and
standard Docker Compose.

The permanent ZimaOS source is:

```text
https://github.com/mattbox03/Clipboard-Bridge-AppStore/archive/refs/heads/main.zip
```

## Server configuration

| Variable | Default | Description |
|---|---:|---|
| `CLIPBOARD_PORT` | `5088` | Listening port |
| `CLIPBOARD_TOKEN` | empty | Optional shared API token |
| `CLIPBOARD_PASSWORD` | empty | Optional web login password |
| `CLIPBOARD_ACCOUNTS` | empty | Comma-separated `user:password` accounts |
| `CLIPBOARD_ACCOUNTS_FILE` | empty | File containing one `user:password` per line |
| `CLIPBOARD_MAX_HISTORY` | `200` | Server history limit |
| `CLIPBOARD_MAX_UPLOAD_MB` | `64` | Maximum upload size |
| `CLIPBOARD_DATA_DIR` | `./clipboard_data` | Persistent data folder |

The shared clipboard remains available when accounts are added. Accounts have separate
histories and there is no fixed account-count limit. For large installations, use
`CLIPBOARD_ACCOUNTS_FILE`.

## Network and security

Clipboard Bridge is designed for private networks.

- Do not expose port `5088` directly to the public internet.
- Use a token or account when other people can access the network.
- Use a VPN for access away from home. Tailscale is one option, not a requirement.
- A VPN works with both the standalone server and Windows Server mode.
- HTTPS termination can be added through a trusted reverse proxy.

With Tailscale, replace the LAN address with the server's private Tailscale address:

```text
http://100.x.y.z:5088
```

See [SECURITY.md](SECURITY.md) before exposing a server beyond a trusted LAN.

## Repository

| Path | Purpose |
|---|---|
| `android/` | Native Android application |
| `clipboard_bridge_windows.py` | Windows client and built-in server |
| `clipboard_bridge-Server.py` | Standalone Flask server and web interface |
| `Iphone Shortcuts/` | Ready-made iOS Shortcuts |
| `Dockerfile`, `compose.yaml` | Container deployment |
| `tests/` | Server and Windows regression tests |
| `docs/` | GitHub Pages website |

## Build and contribute

- Android build: [android/README.md](android/README.md)
- Windows packaging: [build and signing guide](CODE_SIGNING.md)
- Docker deployment: [DOCKER.md](DOCKER.md)
- Contribution rules: [CONTRIBUTING.md](CONTRIBUTING.md)

Clipboard Bridge is released under the [MIT License](LICENSE).
