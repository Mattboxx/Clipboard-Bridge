# Docker and app-store installation

Clipboard Bridge is a single Flask service. It listens on port `5088`, stores
all persistent state in `/data`, exposes `/health`, and requires no database or
sidecar. The image supports `linux/amd64` and `linux/arm64`.

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
**[Clipboard-Bridge-AppStore](https://github.com/mattbox03/Clipboard-Bridge-AppStore)**.
It provides detailed instructions and prepared files for ZimaOS, Portainer,
Umbrel, Runtipi, Docker Compose, Docker Desktop and Dockge.

- [English catalog guide](https://github.com/mattbox03/Clipboard-Bridge-AppStore#readme)
- [Italian catalog guide](https://github.com/mattbox03/Clipboard-Bridge-AppStore/blob/main/README.it.md)
- [Portainer template](https://raw.githubusercontent.com/mattbox03/Clipboard-Bridge-AppStore/main/portainer/templates.json)
- [Permanent ZimaOS source](https://github.com/mattbox03/Clipboard-Bridge-AppStore/archive/refs/heads/main.zip)

## First publication

1. Push this application repository to GitHub.
2. Create and push the release tag: `git tag v1.0.0` then
   `git push origin v1.0.0`.
3. Wait for the **Build container image** workflow to publish the GHCR image.
4. Make the GHCR package public in the package settings.
5. Update the separate `Clipboard-Bridge-AppStore` repository when its manifests
   or installation guides change.

The ZimaOS source URL is permanent:

```text
https://github.com/mattbox03/Clipboard-Bridge-AppStore/archive/refs/heads/main.zip
```

Do not put a release tag in the source URL. New catalog releases are published
to `main`, while the image tag inside the manifest remains pinned until that
application release has been tested.

## ZimaOS installation

1. Open the ZimaOS App Store.
2. Open custom source management.
3. Add the permanent `main.zip` URL above.
4. Restart ZimaOS if it does not refresh the source immediately.
5. Search for **Clipboard Bridge** under **Utilities**.
6. Install it and open `http://ZIMA-IP:5088`.

The ZimaOS data directory is
`/DATA/AppData/clipboard-bridge/data`. The complete end-user procedure is in the
[catalog README](distribution/clipboard-bridge-store/README.md).

## Update and backup

```bash
docker compose pull
docker compose up -d
docker compose ps
```

For a backup, stop the service and copy the directory configured by `DATA_ROOT`.
Restore it to the same location before restarting. Do not run
`docker compose down --volumes` when preserving data.

## Security and accounts

Set `WEB_PASSWORD` and `API_TOKEN` outside a trusted LAN. `ACCOUNTS` accepts an
arbitrary practical number of comma-separated `user:password` pairs. Every
account has isolated history and files.
