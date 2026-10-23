---
title: Share clipboard and files between Windows, iPhone and Android on your own network
published: false
description: Use your Windows PC or an optional Docker host to share text, photos and files with your phone.
tags: opensource, windows, selfhosted, tutorial
canonical_url: https://mattboxx.github.io/Clipboard-Bridge/tutorial.html
---

Moving a copied link between a Windows PC and an iPhone should not require a chat
with yourself. Sometimes a manual file-transfer tool is all you need. If you also
want one retained latest item and a history on a host you control, this tutorial
shows a different workflow using Clipboard Bridge.

I maintain the project; it is MIT-licensed. AI assistants have been used substantially
for implementation, tests and documentation, including preparing this article.

## Start with a host, not a cloud account

Every client connects to the same clipboard host. Choose one:

- **Windows Server mode:** the Windows tray app itself is the host. No NAS or Docker
  installation is required. The PC and application must stay running.
- **Standalone Docker/Python host:** use an always-on server for persistent history,
  browser access and optional separate accounts while your PC is off.

Put the PC and phone on the same trusted Wi-Fi/LAN for the first test. Guest Wi-Fi
may isolate devices. A phone on mobile data cannot reach a home LAN address without
a suitable private network route.

## 1. Make Windows the host

Download the Windows installer or portable EXE from the
[release](https://github.com/Mattboxx/Clipboard-Bridge/releases/tag/2.0.18).
Intel/AMD Windows 10/11 PCs normally need x64; Windows 11 Snapdragon PCs need ARM64.

Open the app. Right-click its clipboard icon near the Windows clock and choose
Settings. In General, select Server mode, keep port 5088 and save. Allow the app
through Windows firewall on your trusted private network when prompted.

The tray menu shows a Server address; click it to copy. A sample is
`http://192.168.1.50:5088`, but use the address your PC actually displays.
On a phone, `localhost` or `127.0.0.1` refers to the phone, not your PC.

Windows Server mode intentionally has **no browser page**. Use History in Windows
and the mobile clients. Left-clicking the tray icon opens History. Its default
`Ctrl+Alt+H` shortcut toggles the window; change it in Settings > Shortcuts.

![Windows clipboard history with sample data](https://mattboxx.github.io/Clipboard-Bridge/assets/windows-history.png)

## 2. Connect iPhone or iPad with two Shortcuts

Download the signed
[Load Clipboard](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.18/iPhone.Load.Clipboard.shortcut)
and
[Download Clipboard](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.18/iPhone.Download.Clipboard.shortcut)
files on your iPhone and add them to Apple's Shortcuts app.

Edit the Get Contents of URL action in each Shortcut:

```text
Send:    POST http://YOUR_HOST:5088/clipboard
Receive: GET  http://YOUR_HOST:5088/clipboard/latest/raw
```

Replace YOUR_HOST with your Windows or Docker host. Keep POST for Send and GET for
Receive. Leave optional credentials empty if your shared trusted-LAN host does not
require them.

Copy `Hello from Windows` on the PC and use Send clipboard in the tray menu. Run
Download Clipboard on iPhone and paste into a blank note. For the opposite direction,
copy text on iPhone, run Load Clipboard, then Receive latest on Windows and paste.

On supported iOS versions, add each Shortcut to Control Center using Add a Control >
Shortcut > Choose. Apple's
[guide](https://support.apple.com/guide/shortcuts/apd06a9201d4/ios) shows that procedure.

For Share Sheet input, original filenames and file groups, follow the
[advanced recipe](https://github.com/Mattboxx/Clipboard-Bridge/blob/main/GUIDE.md#51-send-clipboard-to-server).
The signed exports are unchanged in this release; they must not be assumed to
include the newer group recipe. That variant makes a temporary ZIP, POSTs it to
`/clipboard/bundle`, and checks `/clipboard/latest/meta` before extracting a received
group. A normal ZIP shared as a file is not automatically unpacked by the server.

Apple Shortcuts are **user-triggered actions**, not continuous background clipboard
synchronization. Mac can build the same manual HTTP workflow in Apple Shortcuts;
there is no native Mac client.

## 3. Connect Android

Install the
[signed Android APK](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/android-v1.0.0-beta.12/Clipboard.Bridge.Android.universal.V1.0.0-beta.12.apk).
It requires Android 10 or newer and is a public beta. In the app's settings, enter
the same host address and save. Add credentials only if configured on your host.

Copy a sample message, open Clipboard Bridge and tap Send clipboard. Receive it on
Windows. Send another message from Windows, tap Receive latest on Android, and paste
into a note.

Use Share > Clipboard Bridge in another app for photos and documents. Several files
shared together remain one history item. The history belongs to the selected
server/account, not a separate local-only clipboard list.

The app also has Quick Settings actions and incoming notification options. Android
restricts background clipboard reading: do not expect every copy in another app to
be detected while Clipboard Bridge is in the background. Start with manual transfers,
then enable the optional automation you need.

## 4. Understand the latest-item flow

Text, images, PDFs and arbitrary files all use the same newest-item order. A new text
message takes precedence over an older file group.

Copied rich text arrives as plain Unicode: keep emoji, accents and line breaks, drop
fonts and colours. Actual documents, including RTF files, retain their original bytes.

On Windows, copy files in File Explorer and Send clipboard, or choose Send a file.
Received files are stored under Downloads/Clipboard Bridge and placed on the Windows
clipboard. Some destination apps do not accept file clipboard items; use their file
picker or Share action instead.

Windows and Android can restore file-group members together. A browser/API client
downloads a group as ZIP; Apple needs the extraction variant described above.

Windows History includes image and PDF first-page previews. Configure notifications,
Send/Receive/History hotkeys and optional synchronization in Settings. Automatic
sending can include sensitive clipboard contents, so enable it deliberately.

## 5. Optional: use an always-on Docker host

With Docker and Compose already installed, create `compose.yaml` in an empty project
folder:

```yaml
services:
  clipboard-bridge:
    image: ghcr.io/mattboxx/clipboard-bridge-server:1.0.9
    restart: unless-stopped
    ports:
      - "5088:5088"
    environment:
      CLIPBOARD_DATA_DIR: /data
    volumes:
      - ./data:/data
```

Run:

```bash
docker compose up -d
docker compose ps
```

Open `http://YOUR_HOST:5088/` to use the standalone browser interface. In Windows,
switch to Client mode and set this host address in Settings. Use the same host on
Android and in both Apple Shortcuts.

For custom ZimaOS, Umbrel, Runtipi and Portainer catalog adapters, see the
[App Store repository](https://github.com/Mattboxx/Clipboard-Bridge-AppStore).
These are custom integrations, not claims of official-store acceptance.

Back up your data before updating. Change the image tag but preserve the existing
`/data` mount and environment values. Update or remove an old pinned image digest
when changing versions, then run:

```bash
docker compose pull
docker compose up -d
```

Do not delete the data folder or use `docker compose down -v` as an update command.

## Optional accounts and remote access

The standalone server can isolate accounts without removing the general shared
clipboard. Configure the same username and password in Windows and Android. For
Apple, append the URL-encoded credentials to both action URLs:

```text
http://YOUR_HOST:5088/clipboard?user=alice&password=YOUR_PASSWORD
http://YOUR_HOST:5088/clipboard/latest/raw?user=alice&password=YOUR_PASSWORD
```

These are placeholders. If a URL already contains a query parameter, append with
`&` instead of another `?`. For a protected shared clipboard, use its configured
optional token. See the
[account guide](https://github.com/Mattboxx/Clipboard-Bridge/blob/main/GUIDE.md#multiple-accounts).

**URL credentials are readable, and plain HTTP is not encrypted.** Do not publish
these URLs in screenshots or logs. The app is for a trusted LAN or private VPN, not
direct public exposure. Do not forward port 5088 to the public Internet.

For remote use, Tailscale or WireGuard are examples of private VPNs. Routing and
firewall rules still need to allow the phone to reach the host. A separately
configured subnet router can retain a home LAN address remotely. A VPN protects
its tunnel, not necessarily every local segment. The current Windows client uses
HTTP; do not assume an HTTPS-only reverse proxy works on all clients.

## See Windows and iPhone working together

[Try the steps yourself](https://mattboxx.github.io/Clipboard-Bridge/tutorial.html#demo):
copy and Send on Windows, trigger Receive on iPhone, then paste. Share a photo with
the Send Shortcut to go the other way, then Receive in Windows. These are instructions,
not physical phone footage. The example uses Windows as host, so no separate server is required.

The page also keeps a separate technical recording of the actual standalone
server 1.0.8 on a disposable local instance: save
Unicode text, upload the public project icon, send two files as one group, download
the ZIP, then save newer text.

The web recording uses automated browser actions and captions. Independent HTTP reads
and byte comparisons validate the text, image and both grouped files. It is **not**
a physical-phone or cross-device system-clipboard recording. Physical phone, NAS GUI
and real VPN acceptance checks on the latest builds remain pending.

Automated server/client tests, native Windows packaging and Docker persistence checks
have passed. Windows installers and portable packages are currently unsigned;
do not disable Windows protection to bypass warnings. Read
[CODE_SIGNING.md](https://github.com/Mattboxx/Clipboard-Bridge/blob/main/CODE_SIGNING.md).

Source, downloads and detailed instructions:
[Clipboard Bridge](https://github.com/Mattboxx/Clipboard-Bridge).
If something fails, report versions and reproducible steps, not private clipboard
contents or account URLs.
