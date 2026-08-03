# Clipboard Bridge App Store

**English** | [Italiano](README.it.md)

This repository contains the one-click installation catalog for
[Clipboard Bridge](https://github.com/Mattboxx/Clipboard-Bridge).

## ZimaOS: add the store

Use this permanent URL:

```text
https://github.com/Mattboxx/Clipboard-Bridge-AppStore/archive/refs/heads/main.zip
```

The URL has no release number. It always downloads the current `main` branch,
so it remains the same when the catalog is updated.

### Step by step

1. Open the **App Store** in ZimaOS.
2. Open the source or custom store management screen.
3. Choose **Add source**.
4. Paste the complete `main.zip` URL shown above.
5. Confirm and wait for the import to finish.
6. Restart ZimaOS if the new source does not refresh immediately.
7. Open the App Store again.
8. Search for **Clipboard Bridge** or open the **Utilities** category.
9. Select the application and press **Install**.
10. When installation finishes, open `http://ZIMA-IP:5088`.

Replace `ZIMA-IP` with the local IP address of your ZimaOS machine, for example:

```text
http://192.168.1.50:5088
```

Do not add the normal GitHub repository page as a source. It is HTML, not a ZIP:

```text
https://github.com/Mattboxx/Clipboard-Bridge-AppStore
```

## First configuration

The default installation works without credentials on the local network. For a
safer installation, edit the application environment variables in ZimaOS:

| Variable | Purpose | Example |
|---|---|---|
| `CLIPBOARD_PASSWORD` | Password for the web interface | `change-this-password` |
| `CLIPBOARD_TOKEN` | Token used by Windows and iPhone API requests | `change-this-token` |
| `CLIPBOARD_ACCOUNTS` | Extra isolated users | `alice:pass1,bob:pass2` |
| `CLIPBOARD_MAX_HISTORY` | Maximum stored items | `200` |
| `CLIPBOARD_MAX_UPLOAD_MB` | Maximum size of one upload in MB | `64` |

The shared clipboard always remains available. Extra accounts have separate
history and files. There is no fixed account limit; for many accounts use the
accounts-file method documented in the main project.

## Windows and iPhone

Download or build the Windows client from the
[main project](https://github.com/Mattboxx/Clipboard-Bridge). In client mode,
set:

- server address: the ZimaOS local IP;
- port: `5088`;
- token: the value of `CLIPBOARD_TOKEN`;
- account and password: leave empty for the shared clipboard, or enter an extra
  account configured in `CLIPBOARD_ACCOUNTS`.

For iPhone Shortcuts, the two universal endpoints are:

```text
POST http://ZIMA-IP:5088/clipboard
GET  http://ZIMA-IP:5088/clipboard/latest/raw
```

For an isolated account, append its credentials:

```text
?user=alice&password=pass1
```

Complete example:

```text
http://192.168.1.50:5088/clipboard/latest/raw?user=alice&password=pass1
```

## Update

The store URL never changes. After this repository is updated:

1. refresh the custom source in ZimaOS;
2. if no refresh button is available, remove and re-add the same `main.zip` URL;
3. restart ZimaOS if the cached catalog is still shown;
4. install the update offered for Clipboard Bridge.

Application images are intentionally pinned to a release in the manifest. This
prevents an untested image from replacing a working installation.

## Data and backup

Persistent data is stored in:

```text
/DATA/AppData/clipboard-bridge/data
```

It contains history, uploaded files, account directories and the session key.
Back up the complete directory. To restore it, stop Clipboard Bridge, restore
the directory and start the application again.

Never delete the application data or Docker volumes unless you intentionally
want to erase the history and uploaded files.

## Troubleshooting

### The source is accepted but no app appears

1. Confirm that the URL ends with `/archive/refs/heads/main.zip`.
2. Remove older versioned Clipboard Bridge sources.
3. Add the permanent URL again.
4. Restart ZimaOS.
5. Search the complete store for `Clipboard Bridge`.

### `zip: not a valid zip file`

The normal repository URL was used. Use the `main.zip` URL from the top of this
README.

### The application installs but does not open

Check that port `5088` is free and that the container is running. Then open:

```text
http://ZIMA-IP:5088/health
```

A working server returns a JSON status response.

## Docker Compose, Docker Desktop and Dockge

This method works on any machine with Docker Compose.

```bash
git clone https://github.com/Mattboxx/Clipboard-Bridge-AppStore.git
cd Clipboard-Bridge-AppStore
docker compose up -d
```

Open `http://SERVER-IP:5088`. By default, persistent data is created in the
`data` directory beside `compose.yaml`.

To configure the installation, create a `.env` file in the same directory:

```env
APP_PORT=5088
DATA_ROOT=./data
MAX_HISTORY=200
API_TOKEN=change-this-token
WEB_PASSWORD=change-this-password
ACCOUNTS=alice:pass1,bob:pass2
```

Then apply the configuration:

```bash
docker compose up -d
```

In **Dockge**, create a new stack, paste the contents of `compose.yaml`, add the
same environment variables in Dockge and deploy the stack.

Update:

```bash
git pull
docker compose pull
docker compose up -d
```

## Portainer

Use the ready-made App Template:

```text
https://raw.githubusercontent.com/Mattboxx/Clipboard-Bridge-AppStore/main/portainer/templates.json
```

### Step by step

1. Open **Portainer**.
2. Go to **Settings** and find **App Templates**.
3. Paste the URL above into the App Templates URL field and save.
4. Open **App Templates** from the main menu.
5. Search for **Clipboard Bridge**.
6. Select it and choose the target Docker environment.
7. Set the public port and persistent data directory.
8. Optionally set the API token, web password and additional accounts.
9. Press **Deploy the stack**.
10. Open `http://SERVER-IP:5088`.

If Clipboard Bridge is not listed immediately, reload Portainer after saving
the template URL.

To update, open the stack, pull the latest image specified by the template and
redeploy it without deleting the persistent data directory.

## Umbrel

Use this repository as the Community App Store:

```text
https://github.com/Mattboxx/Clipboard-Bridge-AppStore
```

### Step by step

1. Open the Umbrel App Store.
2. Open **Community App Stores**.
3. Add the repository URL above.
4. Open the new **Clipboard Bridge App Store** source.
5. Select **Clipboard Bridge** and install it.
6. Open the application from Umbrel.

Umbrel generates an application password. The adapter uses that password for
both web access and the API, allowing the Windows client and iPhone Shortcuts
to authenticate. Persistent data is stored below Umbrel's application data
directory.

For updates, refresh the Community App Store and install the update offered by
Umbrel. Do not remove the application data directory.

## Runtipi

This catalog keeps ZimaOS compatibility at its root, so Clipboard Bridge must
be added with Runtipi's official **Add custom app** function. The ready-made
Runtipi files are under:

```text
adapters/runtipi/apps/clipboard-bridge/
```

### Step by step

1. Open **App Store** in Runtipi.
2. Select **Add custom app**.
3. Use `clipboard-bridge` as the app ID and `Clipboard Bridge` as its name.
4. Set the image to `ghcr.io/mattboxx/clipboard-bridge-server:1.0.3`.
5. Set container port `5088` and expose it through Runtipi.
6. Add a persistent volume from `/data` in the container to the app data
   directory proposed by Runtipi.
7. Add `CLIPBOARD_PORT=5088` and `CLIPBOARD_DATA_DIR=/data`.
8. Optionally add `CLIPBOARD_TOKEN`, `CLIPBOARD_PASSWORD` and
   `CLIPBOARD_ACCOUNTS`.
9. Save and install the custom app.

The complete reference configuration is available in
`adapters/runtipi/apps/clipboard-bridge/docker-compose.yml`. To update the
custom app, select the newer Clipboard Bridge image tag and redeploy it without
removing its application data.

## Platform summary

| Platform | Source to add |
|---|---|
| ZimaOS | `https://github.com/Mattboxx/Clipboard-Bridge-AppStore/archive/refs/heads/main.zip` |
| Portainer | `https://raw.githubusercontent.com/Mattboxx/Clipboard-Bridge-AppStore/main/portainer/templates.json` |
| Umbrel | `https://github.com/Mattboxx/Clipboard-Bridge-AppStore` |
| Runtipi | **Add custom app**, using `adapters/runtipi/apps/clipboard-bridge/` |
| Docker/Dockge | `compose.yaml` from this repository |
