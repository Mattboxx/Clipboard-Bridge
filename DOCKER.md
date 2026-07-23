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

The separate
[`distribution/clipboard-bridge-store`](distribution/clipboard-bridge-store)
directory is ready to publish as `Clipboard-Bridge-AppStore`. It contains
ZimaOS/CasaOS, Portainer, Umbrel and Runtipi adapters plus generic Compose.

Create that GitHub repository, copy the directory contents to its root, and push
them to the `main` branch. The exact store URLs and platform-specific steps are
listed in its README.

## First publication

1. Push this application repository to GitHub.
2. Create and push the release tag: `git tag v1.0.0` then
   `git push origin v1.0.0`.
3. Wait for the **Build container image** workflow to publish the GHCR image.
4. Make the GHCR package public in the package settings.
5. Publish the contents of `distribution/clipboard-bridge-store` in the separate
   `Clipboard-Bridge-AppStore` repository.

The store manifests point to `1.0.0`, so the store should be published only after
that image exists.

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
