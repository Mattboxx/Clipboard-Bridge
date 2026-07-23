# Clipboard Bridge App Store

**English** | [Italiano](README.it.md)

This repository contains the one-click installation catalog for
[Clipboard Bridge](https://github.com/mattbox03/Clipboard-Bridge).

## ZimaOS: add the store

Use this permanent URL:

```text
https://github.com/mattbox03/Clipboard-Bridge-AppStore/archive/refs/heads/main.zip
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
https://github.com/mattbox03/Clipboard-Bridge-AppStore
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

The shared clipboard always remains available. Extra accounts have separate
history and files. There is no fixed account limit; for many accounts use the
accounts-file method documented in the main project.

## Windows and iPhone

Download or build the Windows client from the
[main project](https://github.com/mattbox03/Clipboard-Bridge). In client mode,
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

## Other platforms

- Generic Docker, Docker Desktop and Dockge: use `compose.yaml`.
- Portainer template:
  `https://raw.githubusercontent.com/mattbox03/Clipboard-Bridge-AppStore/main/portainer/templates.json`
- Umbrel and Runtipi adapters are available under `adapters/`.

