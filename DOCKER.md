# Install the Docker server from scratch

**English** | [Guida completa in italiano](DOCKER.it.md)

This guide installs Clipboard Bridge **without an app store, Git, Python or a
source build**. You download two small configuration files; Docker downloads and
runs the ready-made server. It works on supported Linux `amd64`/`arm64` hosts and
Docker Desktop using Linux containers. No database is needed.

The server computer must stay on. If you only need a Windows PC and phone setup,
the Windows app's **Server mode** is an alternative that needs no Docker.

Follow the steps in order. Run commands on **the computer that will host the
server**, not on your phone. Do not type the Markdown fences or a `$` prompt.
If a command fails, stop and use [Troubleshooting](#troubleshooting).

- [1. Install and check Docker](#1-install-and-check-docker)
- [2. Create a folder and get the files](#2-create-a-folder-and-get-the-files)
- [3. Configure before starting](#3-configure-before-starting)
- [4. Download and start the server](#4-download-and-start-the-server)
- [5. Open it and connect your devices](#5-open-it-and-connect-your-devices)
- [Update and backup](#update-and-backup)
- [Troubleshooting](#troubleshooting)

## 1. Install and check Docker

**Docker already works on your NAS/server?** Do not reinstall it or remove its
packages. Open its terminal/SSH session and skip to the checks below. On a NAS,
use the manufacturer's supported Docker/Container Manager installation.

### Windows or Mac

1. Install Docker Desktop from the official [Windows instructions](https://docs.docker.com/desktop/setup/install/windows-install/)
   or [Mac instructions](https://docs.docker.com/desktop/setup/install/mac-install/).
   Check the requirements there. Choose the download for your processor.
2. On Windows, follow the installer's WSL 2 instructions and restart if requested.
   Use **Linux containers**, not Windows containers.
3. Start Docker Desktop and wait until its engine is running. Review its terms
   yourself. Compose is included; no separate Compose installation is needed.
4. Open **PowerShell** on Windows or **Terminal** on Mac. Docker Desktop must
   stay running, including after you sign in again following a restart.

### Fresh Ubuntu Server

These commands are for a **fresh supported Ubuntu installation**, not Debian,
other distributions, or a NAS with existing containers. If Docker is already
installed, use the checks instead. For existing/conflicting packages or another
OS, use [Docker's installation selector](https://docs.docker.com/engine/install/).

Run each command in order; `sudo` may ask for your Linux password (nothing is
shown as you type). This uses Docker's [official Ubuntu package repository](https://docs.docker.com/engine/install/ubuntu/):

```bash
sudo apt update
sudo apt install ca-certificates curl nano
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

Paste this entire block, including the last `EOF` line, as one command:

```bash
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

Then install and start the engine and Compose plugin:

```bash
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
```

### Check before continuing

On Docker Desktop:

```text
docker version
docker compose version
```

On Linux, use `sudo` when your user does not have Docker access:

```bash
sudo docker version
sudo docker compose version
```

The first command must show **both Client and Server** without a connection
error. The second must show a Compose version. In the remaining steps, Linux
users who needed `sudo` must prefix **every `docker ...` command** with `sudo`.
Do not change permissions on the Docker socket or add users to groups just to
hide an error. See [Docker's post-installation guidance](https://docs.docker.com/engine/install/linux-postinstall/)
if you intentionally want to change Docker access.

## 2. Create a folder and get the files

Use a **new, empty folder**. Do not download over an existing installation's
`.env` file: that would replace its settings. The public files contain no private
credentials. No GitHub account or `docker login` is required for the public image.

### Windows PowerShell

```powershell
New-Item -ItemType Directory -Path "$HOME\clipboard-bridge"
Set-Location "$HOME\clipboard-bridge"
Invoke-WebRequest -Uri https://raw.githubusercontent.com/Mattboxx/Clipboard-Bridge/main/compose.yaml -OutFile compose.yaml
Invoke-WebRequest -Uri https://raw.githubusercontent.com/Mattboxx/Clipboard-Bridge/main/.env.example -OutFile .env
Get-ChildItem -Force
```

### Linux or Mac terminal

```bash
mkdir ~/clipboard-bridge
cd ~/clipboard-bridge
curl -fL https://raw.githubusercontent.com/Mattboxx/Clipboard-Bridge/main/compose.yaml -o compose.yaml
curl -fL https://raw.githubusercontent.com/Mattboxx/Clipboard-Bridge/main/.env.example -o .env
ls -la
```

You should see **`compose.yaml` and `.env`** in that folder. `.env` starts with a
dot and may be hidden in a file manager; do not rename it to `.env.txt`.
These are the complete Compose template and its settings, not Python source files.

## 3. Configure before starting

Open `.env` in a plain-text editor. On Windows:

```powershell
notepad .env
```

On Linux, use `nano .env` (save with **Ctrl+O**, Enter, then **Ctrl+X**).
On Mac, use `open -t .env` and keep the file as plain text.

Here is a **complete starting configuration**. Use it in `.env`, replacing any
downloaded values; do not paste it into the terminal:

```dotenv
APP_PORT=5088
DATA_ROOT=./data
APP_IMAGE=ghcr.io/mattboxx/clipboard-bridge-server:1.0.10
MAX_HISTORY=200
MAX_UPLOAD_MB=64
API_TOKEN=
WEB_PASSWORD=
ACCOUNTS=
ACCOUNTS_FILE=
SESSION_DAYS=3650
```

**Save before proceeding.** On Linux/Mac, run `chmod 600 .env` to restrict access
to this settings file. This example deliberately starts with an open shared
clipboard: only use it on a trusted private network. Anyone who can reach the
service can read, upload or delete shared content when protection is empty.

| Setting | What to choose |
|---|---|
| `APP_PORT` | Keep `5088`. If occupied, use e.g. `5089`; all device URLs then use `5089`. The container still listens on `5088`. |
| `DATA_ROOT` | Keep `./data` for a new install. This becomes the `data` folder beside `compose.yaml`, mounted as `/data` inside Docker. For NAS/Portainer use an existing, writable absolute host path. Never change an existing data path casually. |
| `APP_IMAGE` | The example pins server `1.0.10`. Docker picks the supported CPU architecture automatically. |
| `MAX_HISTORY` | Retained history entries per shared space/account. Older entries are removed when the limit is exceeded. |
| `MAX_UPLOAD_MB` | Maximum upload **request** size in MB, including a whole file group. `64` is the default. |
| `API_TOKEN` | Optional protection for the shared API used by apps and Shortcuts. |
| `WEB_PASSWORD` | Optional password for the general browser page; does **not** protect the API on its own. |
| `ACCOUNTS` | Optional separate clipboard accounts. Leave empty for the shared clipboard. |
| `ACCOUNTS_FILE` | Optional file for many accounts; leave empty for the first installation. |
| `SESSION_DAYS` | Remember browser logins for 1..3650 days. Choose e.g. `365` for a shorter duration. |

### Optional: protect the general clipboard

Instead of the two empty lines, choose **your own distinct values**, for example:

```dotenv
API_TOKEN='REPLACE_WITH_YOUR_OWN_RANDOM_TOKEN'
WEB_PASSWORD='REPLACE_WITH_YOUR_OWN_WEB_PASSWORD'
```

These are placeholders, not safe ready-made passwords. The web password is for
browser login with an empty username. Set the API token in Windows/Android and
append `?token=YOUR_URL_ENCODED_TOKEN` to both Apple Shortcut URLs.

### Optional: separate accounts

For two different private histories, change just `ACCOUNTS`, using your own passwords:

```dotenv
ACCOUNTS='alice:REPLACE_ALICE_PASSWORD,bob:REPLACE_BOB_PASSWORD'
```

The general clipboard **remains available**. Protect it separately using the two
settings above if needed. An account logs into the browser with its username and
password; native clients use the same account in Settings. This does not create
an online subscription or require an email address.

Single quotes in `.env` keep `$` and `#` literal; do not include a literal single
quote in these simple examples. Use unique account names and no commas/line
breaks in passwords in the comma-separated form. Never publish `.env`, share
credential URLs, or reuse example credentials. See [Security and accounts](#security-and-accounts)
for the account-file option and limitations.

## 4. Download and start the server

Run from the folder containing `compose.yaml` and `.env`. On Linux prefix these
commands with `sudo` if required in step 1.

Validate without printing passwords:

```text
docker compose config --quiet
```

No output and no error means the configuration parsed. Then download the image:

```text
docker compose pull
```

Wait until it finishes successfully. It needs internet access for this download.
Start the server in the background:

```text
docker compose up -d
```

Check its status:

```text
docker compose ps
```

Expect `Up` and eventually **`healthy`** for `clipboard-bridge`; `starting` during
the first minute is normal. If not healthy, inspect recent messages:

```text
docker compose logs --tail=100 clipboard-bridge
```

Do not post unredacted logs or `docker compose config` output: they may expose
clipboard contents, paths or credentials. No Python files need to be copied
into the container, and no manual command inside it is necessary.

## 5. Open it and connect your devices

On the server computer open **`http://localhost:5088/`** in a browser. On a phone,
`localhost` means the phone itself and is **not** the correct address.

Find the host's local network address:

| Host | Command / location |
|---|---|
| Windows | `ipconfig`: use the IPv4 address of the active Wi-Fi/Ethernet adapter, not WSL/Docker/VPN adapters. |
| Linux | `hostname -I`: choose the LAN address, not a Docker bridge address; your router's connected-device list can help. |
| Mac | System Settings > Network > your connected interface > Details > TCP/IP. |
| NAS | Its normal management IP or the router's connected-device list. |

For example, if the host were `192.168.1.50`, use **`http://192.168.1.50:5088/`**
on other devices. This is an example, not an address to copy unchanged. With
`APP_PORT=5089`, replace `5088` with `5089` in **all external URLs** below.
Reserve the host's address in your router (DHCP reservation) to keep it stable.

1. Put the host and phone on the same **trusted local network**, not an isolated
   guest Wi-Fi. The host firewall must permit the selected TCP port from your
   trusted devices. Do not disable the firewall or enable router port forwarding.
   Docker-published ports can bypass some Linux firewall rules: review
   [Docker's firewall notes](https://docs.docker.com/engine/install/ubuntu/#firewall-limitations),
   especially on a VPS/public-facing host. A password does not make HTTP encrypted.
2. Open `http://HOST_IP:5088/health` on the phone. Expect JSON with a healthy status
   and server version. This checks basic reachability, not every account's login.
3. Open `http://HOST_IP:5088/`. If configured, log into the general clipboard with
   a blank username and `WEB_PASSWORD`, or use an account's credentials.
4. **Windows:** Settings > General > **Client mode**, then Connection: enter
   `http://HOST_IP:5088`. Set an optional shared token or account and check connection.
   Do not enable Windows Server mode when connecting to this Docker host.
5. **Android:** Settings: enter the same base address, select Shared space or Account,
   enter any configured credentials, test and save.
6. **Apple Shortcuts:** import [Send and Receive](README.md#download).
   Set Send to `POST http://HOST_IP:5088/clipboard` and Receive to
   `GET http://HOST_IP:5088/clipboard/latest/raw`. **These are URL fields inside
   the Shortcuts, not terminal commands.** Keep the body/copy actions from the
   [complete Apple guide](GUIDE.md#5-set-up-iphone-shortcuts).

For an account, both Shortcut URLs become:

```text
http://HOST_IP:5088/clipboard?user=alice&password=YOUR_URL_ENCODED_PASSWORD
http://HOST_IP:5088/clipboard/latest/raw?user=alice&password=YOUR_URL_ENCODED_PASSWORD
```

For the protected shared clipboard, use `?token=YOUR_URL_ENCODED_TOKEN` instead.
With no protection configured, add nothing. Percent-encode credential values
(e.g. `&` becomes `%26`), not the entire URL. Adding `user` selects an account;
it is not a folder added to the URL path. URL values are readable and HTTP sends
them unencrypted. Never paste your real URLs into public issues.

**First transfer:** save a harmless note such as `Clipboard Bridge test` in the
browser, then Receive on your phone. Send a different note from the phone and
refresh browser history. Use the **same space/account** on all devices. Try a
small photo/file next. No automatic iPhone background sync is implied.

Away from home, connect host and devices through a private VPN such as Tailscale;
use the reachable VPN address. For the same LAN IP inside/outside the house, a
separately configured subnet router is needed. See the [network guide](GUIDE.md#local-network-vpn-and-subnet-routing).
Do **not** expose the port directly to the internet.

## Connect your devices and choose a language

The page header offers English (default), Italian, Spanish, French, German,
Portuguese and simplified Chinese. The selection is remembered for this browser,
including the login page. It does not change clipboard text or file contents.

Expand **Connect your devices** above the text editor for the server address and
step-by-step Windows, Android and Apple Shortcuts instructions. Project website,
downloads, full tutorial and optional Ko-fi support are linked without forwarding
your account credentials. Full external guides remain available in English and Italian.

For a source-only Python deployment, keep `server_web_strings.json` beside
`clipboard_bridge-Server.py`, `clipboard_text.py` and `clipboard_storage.py`.
The Docker image already includes these files; no language packs are needed.

## Image tags

- `edge`: successful build from `main`
- `X.Y.Z`: exact release
- `X.Y`: latest patch of a minor release
- `latest`: latest stable release

Production and store installations should pin an exact `X.Y.Z` tag.

## One-click stores

The ready-to-use catalog is published in
**[Clipboard-Bridge-AppStore](https://github.com/Mattboxx/Clipboard-Bridge-AppStore)**.
It provides detailed instructions and prepared files for ZimaOS, Portainer,
Umbrel, Runtipi, Docker Compose, Docker Desktop and Dockge.

- [English catalog guide](https://github.com/Mattboxx/Clipboard-Bridge-AppStore#readme)
- [Italian catalog guide](https://github.com/Mattboxx/Clipboard-Bridge-AppStore/blob/main/README.it.md)
- [Portainer template](https://raw.githubusercontent.com/Mattboxx/Clipboard-Bridge-AppStore/main/portainer/templates.json)
- [Permanent ZimaOS v2 JSON source](https://mattboxx.github.io/Clipboard-Bridge-AppStore/store.json)

## For maintainers: first publication

1. Push this application repository to GitHub.
2. Create and push the release tag: `git tag vX.Y.Z` then
   `git push origin vX.Y.Z`.
3. Wait for the **Build and publish container** workflow to publish the GHCR image.
4. Make the GHCR package public in the package settings.
5. Update the separate `Clipboard-Bridge-AppStore` repository when its manifests
   or installation guides change.

The generated ZimaOS v2 source URL is permanent:

```text
https://mattboxx.github.io/Clipboard-Bridge-AppStore/store.json
```

Do not use the repository ZIP or put a release tag in the source URL. The
AppStore repository builds `store.json`, `index.json` and the per-app files on
every update to `main`, while the image tag inside the manifest remains pinned
until that application release has been tested.

## ZimaOS installation

1. Open the ZimaOS App Store.
2. Open custom source management.
3. Add the permanent `store.json` URL above.
4. Refresh the App Store if the source does not appear immediately.
5. Search for **Clipboard Bridge** under **Productivity**.
6. Install it and open `http://ZIMA-IP:5088`.

The ZimaOS data directory is
`/DATA/AppData/clipboard-bridge/data`. The complete end-user procedure is in the
[catalog README](https://github.com/Mattboxx/Clipboard-Bridge-AppStore#readme).

## Update and backup

### Back up before changing anything

Return to your installation folder (`cd ~/clipboard-bridge` in Linux/Mac, or
`Set-Location "$HOME\clipboard-bridge"` in PowerShell). Do not repeat the initial
downloads: keep your current `.env` and data. If you used another folder, use it here.

Stop writes before making a consistent copy:

```text
docker compose stop
```

On Linux/Mac, for the default `DATA_ROOT=./data`:

```bash
mkdir -m 700 ../clipboard-bridge-backup-before-update
sudo cp -a data compose.yaml .env ../clipboard-bridge-backup-before-update/
```

On Windows PowerShell:

```powershell
New-Item -ItemType Directory -Path ..\clipboard-bridge-backup-before-update
Copy-Item -Recurse -Path data,compose.yaml,.env -Destination ..\clipboard-bridge-backup-before-update
```

Use a **new backup folder name each time**; do not merge over an earlier backup.
If `DATA_ROOT` is different, copy that actual directory instead of `data`.
Backups include credentials, uploaded files, every user's history and `secret.key`;
keep them private, ideally on another disk. If backing up fails, do not update;
restart the existing service with `docker compose start` while investigating.

### Install a newer server release

1. Read the [server release notes](https://github.com/Mattboxx/Clipboard-Bridge/releases)
   and choose a **published server** version (Windows/Android numbers are separate).
2. Open `.env` as in step 3. Change **only** `APP_IMAGE` to the desired full image
   tag, keeping the same `DATA_ROOT`, credentials and port. Current stable:
   `APP_IMAGE=ghcr.io/mattboxx/clipboard-bridge-server:1.0.10`.
3. Save, then run these commands in order (with `sudo` on Linux if needed):

```text
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
```

Wait for `healthy`, reopen `/health`, check your version and history, then try a
send/receive. If downloading fails after the backup, `docker compose start` can
start the existing stopped container; investigate before recreating it.

**A pinned `1.0.10` tag does not advance to the next release when you run `pull`.**
Change it first. `latest` follows stable releases when pulled but does not update
a running container by itself; pinning makes upgrades deliberate. Do not use
`edge` for a beginner's stable installation.

### Change settings, stop or restore

- After editing `.env`, run **`docker compose up -d`** to apply it. A simple
  `docker compose restart` does not apply changed container environment variables.
- Stop temporarily: `docker compose stop`. Start the same container: `docker compose start`.
  `restart: unless-stopped` handles engine restarts unless you stopped the container;
  on a PC, Docker Desktop must start too.
- To remove the container but keep this bind-mounted data: `docker compose down`.
  Recreate later with `docker compose up -d`, in the same folder with the same `.env`.
  **Do not add `--volumes`, delete the data folder, or run cleanup/prune commands.**
- To restore: stop the service; preserve a separate copy of the current data first.
  Restore the **whole** backup data directory to the configured `DATA_ROOT`, plus
  its `.env` and Compose file. Use the image version recorded in that backup;
  then run `docker compose up -d` and check history. Do not mix pieces from
  different backup dates or assume an older server can read newer data.

## Troubleshooting

Run checks from the installation folder. On Linux apply the same `sudo` rule as
before. Do not remove old settings/data to make an error disappear.

| Symptom | What to check |
|---|---|
| `docker: command not found` / not recognized | Install Docker for that host, then reopen the terminal. |
| Only Client appears / cannot connect to daemon | Start Docker Desktop; on Ubuntu check `sudo systemctl status docker` (press `q` to exit). |
| Permission denied on the Docker socket | Retry the command with `sudo` on Linux; do not use `chmod 777`. |
| `compose` not recognized | Install the official Compose plugin or update Docker Desktop; use `docker compose`, not the legacy `docker-compose`. |
| `no configuration file provided` | You are in the wrong folder. List files with `ls -la` or `Get-ChildItem -Force`; locate `compose.yaml`. |
| Invalid YAML / interpolation error | Redownload **only the public template** if corrupted; preserve `.env`. Check spelling, single quotes and plain-text format. `config --quiet` validates without dumping secrets. |
| Name `clipboard-bridge` already in use | Check `docker ps -a`. Locate the existing install; do not delete its container or run a second host on its data. This guide assumes one installation. |
| Port already allocated | Change `APP_PORT=5089` in `.env`, run `docker compose up -d` and update every device URL. Check the Windows app is not already hosting on the same port. |
| Image not found / access denied | Check the public image name and published tag, internet/DNS/proxy access to GHCR. No private GitHub token is needed. |
| `no matching manifest` | The image supports Linux amd64/arm64, not 32-bit ARM or Windows containers. Choose a supported host/Linux-container engine. |
| `unhealthy`, restart loop, storage errors | Run `docker compose logs --tail=100 clipboard-bridge`; check disk space and that the data directory is present and writable. Do not use world-writable permissions or delete an index. See below. |
| Works on host, not on phone | Use host LAN IP, not `localhost` or container IP; check same LAN, guest isolation, firewall, port mapping and `/health`. Do not forward the port on the router. |
| 401 / different history on different devices | Match shared-space token or account credentials everywhere. A web login does not log your phone apps in. Encode URL credentials; don't put them in public screenshots. |
| Changed `.env` but nothing changed | Save and run `docker compose up -d`; `restart` alone is insufficient. |
| 413 / upload rejected | Check `MAX_UPLOAD_MB`, including all group members; a reverse proxy may also impose its own size limit. |

For a bug report include OS, server version, steps and **redacted** error messages,
never real credentials, `.env`, personal files or a complete configuration dump.

### History storage errors

The storage-integrity guard fails closed when an existing `index.json`
is unreadable, invalid JSON, or not a list of objects. History endpoints return
`503` with `code: history_unavailable` instead of silently starting an empty
history. Uploads and deletes do not replace the damaged index, and newly staged
upload files are removed. Other healthy accounts remain usable.

1. Stop the service. Copy the **whole** data directory to a separate backup before
   attempting repairs, including `items/`, every `users/` directory and `secret.key`.
2. Check free disk space, volume availability and the container's read/write
   permissions. Do not print credential URLs or personal clipboard data in a bug report.
3. If the index is damaged, restore a consistent backup of the affected space
   together with its referenced files. Do not delete the index to dismiss the error:
   that loses the history references and is not a repair.
4. Start the service and check `/health` and the affected account's history.
   `/health` checks the shared store; success does not certify every account.

There is no automatic backup or guaranteed recovery of files already lost to a
disk failure. Flushing a temporary index before an atomic rename helps preserve
the last committed state; it does not replace backups or guarantee power-loss
durability on every filesystem. One process owns the JSON store; independent
Gunicorn workers or multiple containers must not write to the same data directory.

Windows uses the same protections for its embedded host and local history.
Quit the app before backing up or restoring its per-user data directory.
If only the optional Windows local history is damaged, a localized warning is
shown without blocking healthy remote sending/receiving or saving Settings.

## Security and accounts

`API_TOKEN`, `WEB_PASSWORD` and `ACCOUNTS` are optional. With all three empty, the
general shared clipboard remains open. Set `WEB_PASSWORD` and `API_TOKEN` outside a
trusted LAN. `ACCOUNTS` accepts an
arbitrary practical number of comma-separated `user:password` pairs. Every
account has isolated history and files. URL credentials remain supported for
iPhone Shortcuts; API clients can alternatively use the `X-Clipboard-User` and
`X-Clipboard-Password` headers.

Accounts are loaded at startup. For changes in `.env`, run `docker compose up -d`;
for changes to the contents of an already mounted account file, restart the service.
For many users, create `accounts.txt` in the host data directory (one
`user:password` per line), set `ACCOUNTS_FILE=/data/accounts.txt` in `.env`, and
run `docker compose up -d`. `/data/accounts.txt` is the **container path**; no extra
mount is needed when the file is inside `DATA_ROOT`. It extends/overrides `ACCOUNTS`.
Keep this file private and use a plain-text editor, not a word processor.
For portable deployments, choose names that do not differ only by letter case or
trailing dots. Such names can refer to one directory on Windows or a case-insensitive
NAS volume. The account-storage guard returns `503` with
`code: account_storage_conflict` rather than allowing those accounts to share data.
The shared space and unrelated users remain available. A healthy case-sensitive
filesystem keeps existing distinct directories and behavior unchanged.

To resolve a conflict, stop the host and back up all affected directories first.
Review the configured names and choose unambiguous ones. If accounts have already
shared a directory, do not automatically assign its mixed history to another user:
review and separate or securely archive it before restoring access. The guard does
not rename directories, migrate or delete data, or change Shortcut credential URLs.
`account_storage_unavailable` instead indicates a directory/permissions problem.

Remembered web logins keep the existing 3650-day default for compatibility.
Set `CLIPBOARD_SESSION_DAYS` to a value from 1 to 3650, for example 90 on a shared
computer or 365 at home. Add it to the service's environment if using a store
manifest. Logout or clearing cookies ends that device's session. Shorter expiry
does not encrypt cookies or provide immediate revocation after a password change.

Query parameters such as `?token=...` and `?user=...&password=...` expose their values
in plain text in the URL. HTTP also sends them without transport encryption. Do not
publish port `5088` directly on the Internet; use a trusted LAN, private VPN or HTTPS
reverse proxy.

The server does not restrict file extensions. The universal `/clipboard` endpoint accepts
raw iOS Shortcut bodies, multipart uploads and JSON/Base64, preserving the original bytes,
Unicode filename and MIME type. Increase `MAX_UPLOAD_MB` when transferring larger files.
