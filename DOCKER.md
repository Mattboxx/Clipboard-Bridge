# Docker and app-store installation

Clipboard Bridge is a single Flask service. It listens on port `5088`, stores
all persistent state in `/data`, exposes `/health`, and requires no database or
sidecar. The image supports `linux/amd64` and `linux/arm64`.

Current stable server image:

```text
ghcr.io/mattboxx/clipboard-bridge-server:1.0.8
```

## Docker Compose

```bash
cp .env.example .env
docker compose up -d
```

Open `http://SERVER-IP:5088` and configure credentials in `.env`.

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

## First publication

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
5. Search for **Clipboard Bridge** under **Utilities**.
6. Install it and open `http://ZIMA-IP:5088`.

The ZimaOS data directory is
`/DATA/AppData/clipboard-bridge/data`. The complete end-user procedure is in the
[catalog README](https://github.com/Mattboxx/Clipboard-Bridge-AppStore#readme).

## Update and backup

```bash
docker compose pull
docker compose up -d
docker compose ps
```

For a backup, stop the service and copy the directory configured by `DATA_ROOT`.
Restore it to the same location before restarting. Do not run
`docker compose down --volumes` when preserving data.

### History storage errors

The unreleased storage-integrity update fails closed when an existing `index.json`
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

Windows uses the same protections for its embedded host and local history in the
candidate update. Quit the app before backing up or restoring its per-user data
directory. Existing releases do not yet include this update.
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

Accounts are loaded at startup; restart the host after editing their configuration.
For portable deployments, choose names that do not differ only by letter case or
trailing dots. Such names can refer to one directory on Windows or a case-insensitive
NAS volume. The unreleased account-storage guard returns `503` with
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
