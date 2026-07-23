# Clipboard Bridge App Store

One-click installation manifests for **Clipboard Bridge**. Application code and
container images are maintained in
[Clipboard-Bridge](https://github.com/mattbox03/Clipboard-Bridge).

Image: `ghcr.io/mattbox03/clipboard-bridge-server:1.0.0`  
Architectures: `linux/amd64`, `linux/arm64`

## Generic Docker, Docker Desktop and Dockge

```bash
git clone https://github.com/mattbox03/Clipboard-Bridge-AppStore.git
cd Clipboard-Bridge-AppStore
docker compose up -d
```

Open `http://SERVER-IP:5088`. Configure environment values before deployment.

## ZimaOS

Add this custom app-store archive:

`https://github.com/mattbox03/Clipboard-Bridge-AppStore/archive/refs/heads/main.zip`

The persistent data directory is managed under `/DATA/AppData`.

## Portainer

Set this URL under **App Templates**:

`https://raw.githubusercontent.com/mattbox03/Clipboard-Bridge-AppStore/main/portainer/templates.json`

## Umbrel

Add this Community App Store:

`https://github.com/mattbox03/Clipboard-Bridge-AppStore`

Umbrel's generated app password is used for both web and API access.

## Runtipi

Use this repository as a custom store:

`https://github.com/mattbox03/Clipboard-Bridge-AppStore`

## Update

```bash
docker compose pull
docker compose up -d
```

Store adapters pin exact release tags. Update the manifest only after publishing
the corresponding container version.

## Backup

Stop the container and back up the entire persistent `data` directory. It
contains history, uploaded files, account data and the session key. Restore it
to the same path before restarting.

Never use `docker compose down --volumes` unless you intend to delete all data.

## Security

Set `CLIPBOARD_PASSWORD` for the browser and `CLIPBOARD_TOKEN` for API clients.
Extra accounts use `CLIPBOARD_ACCOUNTS=user1:pass1,user2:pass2`. Do not expose
the service directly to the public Internet; use a trusted LAN, VPN or protected
reverse proxy.
