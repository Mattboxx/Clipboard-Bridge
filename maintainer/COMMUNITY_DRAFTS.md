# Community drafts: review before posting

No post or submission has been sent. Replace candidate versions with the approved
public versions, attach a real verified demo, recheck live community rules, and
publish only after maintainer approval. Disclose AI assistance where required;
do not submit AI-generated material to communities that prohibit it.

## r/selfhosted

**Title:** I built Clipboard Bridge: a local clipboard and file hub for Windows, Android and iPhone

I wanted a straightforward way to move a link, photo or document between my Windows
PC and phone without sending it to myself through a chat service.

Clipboard Bridge uses one clipboard host on your own network. You can let the Windows
tray app be the host, or run the small Python/Docker service on an always-on server.
The Docker option adds a browser page, persistent server history and optional isolated
accounts. Text, photos and files share the same latest-item flow, and several files
sent together stay in one history entry.

Windows has configurable Send, Receive and History hotkeys and optional synchronization.
Android has a native app, Share target, Quick Settings actions and incoming notifications.
iPhone/iPad use two Apple Shortcuts; Mac can use the same manual API workflow.

There are deliberate limits: iPhone actions are not continuous background sync, and
Android restricts background clipboard access. The Windows downloads are currently
unsigned. This is a trusted-LAN/private-VPN tool, not a service to expose publicly.
HTTP is supported locally; an optional account/token does not encrypt the connection.

No online account, subscription or project-hosted clipboard service is required.
The source is MIT-licensed:

https://github.com/Mattboxx/Clipboard-Bridge

Setup and downloads: https://mattboxx.github.io/Clipboard-Bridge/

I would appreciate feedback on the first setup and the first transfer, especially
from people using a NAS plus both Apple and Android devices. Please report versions
and steps, not private clipboard contents or credential URLs.

**Before posting:** attach the real demo, verify the permitted project flair/day,
state your development involvement honestly, and be available to answer questions.

## Other Reddit communities: tailored angles

These are distinct starting points, not permission to cross-post one advertisement.

| Community | Proposed title | Useful focus |
|---|---|---|
| r/opensource | A MIT-licensed clipboard hub with Windows hosting and Apple Shortcuts | Explain the small HTTP API, contribution guide and currently unsigned binaries; ask for review, not stars |
| r/windows | A configurable tray clipboard bridge to Android and Apple Shortcuts | Show History toggle, previews and standard-user install; disclose signing warnings |
| r/Android | Android clipboard sharing with a private Windows or Docker host | Show Share/Quick Settings; explain Android 10+ background limitations and beta status |
| r/homelab | A small persistent clipboard hub for a home Docker host | Show volume persistence, upgrade/rollback and LAN/VPN boundaries |
| r/raspberry_pi | Sharing a clipboard through an ARM64 Docker host | First record a real Pi deployment; do not label CI/QEMU tests as a physical Pi test |

Check each community's current rules and appropriate weekly/developer thread first.
If uncertain, ask moderators rather than posting and assuming it is allowed.

## selfh.st listing brief

**Name:** Clipboard Bridge

**Short description:** Clipboard and file sharing between Windows, Android and Apple Shortcuts through a host you control.

**Long description:** Clipboard Bridge exchanges Unicode text, photos, arbitrary files
and ordered file groups through a Windows-hosted or standalone Python/Docker clipboard.
The standalone service retains history, exposes a browser interface and supports
optional isolated accounts. Windows provides a tray app, configurable hotkeys and
optional synchronization. Android provides a native Share target, Quick Settings
actions and configurable notifications. Apple devices use manual Shortcuts. Designed
for trusted LANs and private VPNs, without mandatory cloud accounts or telemetry.

- Repository: https://github.com/Mattboxx/Clipboard-Bridge
- Website: https://mattboxx.github.io/Clipboard-Bridge/
- License: MIT
- Docker image: use the approved stable `ghcr.io/mattboxx/clipboard-bridge-server` tag
- Docker guide: https://github.com/Mattboxx/Clipboard-Bridge/blob/main/DOCKER.md
- Platforms: Windows 10/11 x64; Windows 11 ARM64; Android 10+; Apple Shortcuts;
  Docker host linux/amd64 or linux/arm64
- Icon: repository `docs/icon.svg`
- Screenshots: approved sample-only files under `docs/assets/`; verify before uploading
- Caveats: Android beta/background limits; manual Apple actions; unsigned Windows files

Submission route: [selfh.st submit form](https://selfh.st/submit/). Choose the directory
option and review its current fields. Do not include a private maintainer email or
credentials without deciding which contact information may be public.

## Dev.to article draft

**Title:** How to share files and clipboard between Windows and iPhone without iCloud

Moving a copied link from a Windows PC to an iPhone should not require pasting it into
a chat with yourself. File transfer tools already solve many nearby-device workflows;
the harder part is choosing a simple clipboard workflow that fits both operating systems.

Before adding another tool, consider what you actually need. LocalSend is a good starting
point for manual nearby file/text transfers. KDE Connect documents clipboard, file and
notification features. Clipboard Bridge takes a different approach: one retained latest
item and history on a host you control, accessible by a small HTTP API.

### Choose a host

The quickest route is a Windows PC. Install Clipboard Bridge, open Settings, choose
Server mode, and copy the address shown by the application. The PC and app must stay
running. No separate NAS or Docker installation is needed.

For an always-on host, use Docker Compose. Clone the repository, copy `.env.example`
to `.env`, choose a persistent `DATA_ROOT`, and run:

```bash
docker compose up -d
docker compose ps
```

Open the host's address on port 5088. Configure the same base address in your other
clients. Do not delete the data volume during updates. The standalone host adds web
history and optional per-user spaces; it is not a mandatory cloud backend.

### Two iPhone actions

Install the signed Send and Receive Shortcuts from the approved release. Replace the
example address in each Get Contents of URL action:

```text
Send:    POST http://HOST:5088/clipboard
Receive: GET  http://HOST:5088/clipboard/latest/raw
```

Leave account/token parameters absent for a shared trusted-LAN clipboard. When the
administrator has configured an account, append the same URL-encoded `user` and
`password` parameters to both actions. Existing URLs remain supported; no interactive
login or pairing step is added. Keep these URLs out of screenshots.

Copy a non-sensitive link on Windows and send it. Run Receive on iPhone, then paste
the result into a note. To go the other way, copy text or share a photo to Send and
receive on Windows. Show these actual button/Shortcut actions in a demo instead of
presenting them as fully automatic iPhone synchronization.

For several files, the documented Shortcut variant creates a transport ZIP and uses
`/clipboard/bundle`. The server stores one ordered group; the receiving Shortcut checks
metadata before extracting it. A ZIP deliberately sent as a normal file remains a ZIP.

### Text and files have different promises

Copied rich text is delivered as ordinary Unicode text by the updated host: retain
emoji and accents, discard fonts and colours. A document shared as a file keeps its
original bytes, including an actual `.rtf` document. Always include the original filename
for unusual file extensions. Some destination apps cannot paste files from the system
clipboard; use their Share or file picker instead.

### Remote use without opening a public port

Use a trusted LAN, or connect the devices through a private VPN. Tailscale and WireGuard
are examples, not project dependencies. Routing and firewall rules must allow the phone
to reach the host. A home subnet router can preserve a LAN address remotely, but its
route must be configured and approved separately. Do not forward port 5088 publicly.

Plain HTTP is intentionally supported on the LAN. It does not encrypt content or URL
credentials. A VPN protects its tunnel, not necessarily every LAN segment. HTTPS is an
optional endpoint for Android/Apple; the current Windows client uses HTTP, so do not
assume an HTTPS-only proxy automatically works for every client.

### Limitations worth knowing

Windows can optionally synchronize while running. Android provides notifications and
visible-app detection, but Android 10+ restricts background clipboard reads. Apple
Shortcuts run when you trigger them. Windows packages are currently unsigned and may
be blocked by Windows policies; do not disable security to work around a warning.

Start with one manual text transfer, then add automatic options only when you understand
where the data goes. Clipboard history itself may contain private information; protect
the host and its backups.

Source, downloads and detailed instructions:
https://github.com/Mattboxx/Clipboard-Bridge

**Editorial gate:** replace future-version wording with approved versions, attach a
real transfer example, validate every link, and review the article personally before posting.

## Show HN draft

**Title:** Show HN: Clipboard Bridge, a local clipboard hub for Windows, Android and Apple Shortcuts

**Submission URL:** https://github.com/Mattboxx/Clipboard-Bridge

**First comment draft:**

I made this to exchange copied text and files between my Windows PC and phones using
one host on my own network. The host can be the Windows app itself or a small Docker
service, with retained history and optional user spaces. Android has a native app;
Apple uses two Shortcuts, so I am not claiming continuous background sync on iPhone.

The source is MIT-licensed and the API is intentionally small. No online account is
required. It is intended for a trusted LAN/private VPN, not direct public exposure.
Windows binaries are currently unsigned. I would like feedback on the first setup,
file-group behavior and what is confusing in the device instructions.

**Hold until:** the real demo, beginner installation pilot, working public downloads
and maintainer approval are all complete. Do not submit a patch-release announcement
alone as a new Show HN, and do not ask anyone to upvote.

## AlternativeTo listing draft

**Name:** Clipboard Bridge (Mattboxx)

**Website:** https://mattboxx.github.io/Clipboard-Bridge/

**Summary:** Share text, photos and files through a private clipboard host on Windows or Docker.

**Description:** Open-source clipboard and file sharing for Windows, Android and Apple
Shortcuts. Run Windows as the host or use a standalone Docker/Python service for web
history and optional isolated accounts. Supports Unicode text, photos, arbitrary files
and grouped transfers over a trusted LAN/private VPN. No mandatory cloud account.
Automation differs by platform: optional Windows sync, Android foreground restrictions,
manual Apple Shortcuts. Windows packages are currently unsigned.

**Candidate categories/tags:** clipboard tools, file sharing, self-hosted, local network,
Windows, Android, Apple Shortcuts, Docker. Do not label it a native macOS/iOS app.

Check the current site taxonomy and existing names before submitting. A search finding
no matching Mattboxx listing is not proof that no duplicate entry exists.
