# Clipboard Bridge: CasaOS submission package

Prepared on **2026-10-27** for server **1.0.11**:
`ghcr.io/mattboxx/clipboard-bridge-server:1.0.11`.
This is a local preparation package, not evidence that any store accepted the app.
No upstream PR or issue has been submitted by preparing these files.
Version 1.0.11 adds visible top-of-page GitHub and localized optional Ko-fi links;
never submit these proposals before that exact image has been published and checked.

## Submission status

| Store | Correct route | Files / limitation |
|---|---|---|
| Big Bear CasaOS | PR to `bigbeartechworld/big-bear-universal-apps`, branch `main` | Submit `big-bear/universal/apps/clipboard-bridge/`. The CasaOS YAML is generated, not the canonical source. |
| LinuxServer AppStore | Maintainer inquiry **only if needed** | Its README explicitly asks for no PRs; generated catalog of LinuxServer.io images. Our image is independent. See `linuxserver/ISSUE_DESCRIPTION.md`. |
| mr-manuel HomeAutomation | Scope check, then candidate PR to `master` if welcomed | Copy `homeautomation/Apps/ClipboardBridge/`. This is a companion homelab utility, not device automation; acceptance is the maintainer's decision. |

Sources and immutable research references: [UPSTREAMS.md](UPSTREAMS.md).
Do not submit three identical Compose files or claim LinuxServer.io affiliation.

## 1. Big Bear: canonical submission and rendered CasaOS file

Copy the following **contents of `big-bear/universal/`** into your fork of
`bigbeartechworld/big-bear-universal-apps`:

```text
apps/
  clipboard-bridge/
    app.json
    docker-compose.yml
    README.md
```

The universal Compose is deliberately clean: **no `x-casaos`** and no obsolete
Compose `version:` declaration. Metadata belongs in `app.json` and validates
against the actual upstream `app-schema-v1.json`. Only CasaOS conversion is
declared supported in this proposal; other platform flags are false rather than
claiming untested integrations. Existing independent Clipboard Bridge store
adapters are not replaced by this submission.

In your Big Bear fork, install the tools listed by its README (`jq`, Mike Farah
`yq` v4 and Bash; Perl is used by the converter), then run:

```bash
bash scripts/validate-apps.sh -a clipboard-bridge --strict
bash scripts/convert-to-platforms.sh -a clipboard-bridge -p casaos
```

The generated file is `converted/casaos/clipboard-bridge/docker-compose.yml`.
Its downstream CasaOS repository layout is:

```text
Apps/
  clipboard-bridge/
    docker-compose.yml
```

An actual upstream-converter output is included at
[big-bear/casaos-reference/Apps/clipboard-bridge/docker-compose.yml](big-bear/casaos-reference/Apps/clipboard-bridge/docker-compose.yml).
It includes `big-bear-` naming, `com.bigbeartechworld.clipboard-bridge`,
architectures, `main: app`, developer/author, descriptions, screenshots,
service-level environment/volume/port descriptors and port `5088`.
**Do not hand-edit or PR this rendered copy into the generated store** unless
Big Bear specifically asks you to. Let its pipeline handle catalog/README synchronization.

The generated `/DATA/AppData/$AppID/data` is a CasaOS substitution. For a terminal
Compose check, supply `AppID=big-bear-clipboard-bridge`; do not let plain Compose
expand an unset variable to `/DATA/AppData//data`. The clean universal source
uses its own named volume when run directly.

PR title/body: [big-bear/PR_DESCRIPTION.md](big-bear/PR_DESCRIPTION.md).

## 2. LinuxServer: do not submit a fabricated integration

The current target is `WisdomSky/LinuxServer-AppStore` (`main`); the former
`CasaOS-LinuxServer-AppStore` name redirects there. Its catalog is generated and
its README currently declines PRs. It is not a general-purpose third-party image
catalog or a combined list into which arbitrary images can be inserted.

There is **no valid direct app PR for this project under that published policy**.
Adding a service named `linuxserver` or an `lscr.io/linuxserver/clipboard-bridge`
image URL would not make an official image exist. This package does not do that.

`PUID` and `PGID` are interpreted by LinuxServer image initialization code. Our
`python:3.12-slim-bookworm` image has no such entrypoint: putting those variables
in `environment:` would **not** change its user or repair volume permissions.

For reference only, [linuxserver/custom-import/docker-compose.yml](linuxserver/custom-import/docker-compose.yml)
is a valid independent deployment using Docker's real
`user: "${PUID:-1000}:${PGID:-1000}"`. Here the two names are **host-side Compose
variables**, not image features. `TZ=Etc/UTC` is passed as a container setting;
no LinuxServer timezone/ownership initialization is claimed. UTC is the tested
setting; other timezone names require the appropriate timezone data in the image.

For a **new** Linux terminal deployment of that reference:

```bash
cp .env.example .env
id -u
id -g
nano .env
```

Set `PUID`/`PGID` to the intended existing Linux user's numeric IDs. For the
default example only, create a **new, unused** host folder owned by those IDs:

```bash
sudo install -d -m 0750 -o 1000 -g 1000 /DATA/AppData/clipboard-bridge-uid-example/data
docker compose config --quiet
docker compose pull
docker compose up -d
```

Change `1000` to your chosen IDs. Do not recursively chown an existing clipboard
data directory. The image will not chown it for you. Prefix Docker commands with
`sudo` if your host requires it. For CasaOS's YAML import, a neighboring `.env`
file is **not** uploaded automatically: edit `user`, published port and the host
volume path directly, using real values, before importing. This is a manual
import example, **not an upstream LinuxServer AppStore submission**.

If you want to ask about an officially supported route, use
[linuxserver/ISSUE_DESCRIPTION.md](linuxserver/ISSUE_DESCRIPTION.md) as a polite
eligibility inquiry, not a PR against generated app files.

## 3. HomeAutomation: proposed repository overlay

Copy the **contents of `homeautomation/Apps/`** into the upstream `Apps/` folder:

```text
Apps/
  ClipboardBridge/
    docker-compose.yml
    README.md
    icon.png
    screenshot-1.png
    screenshot-2.png
```

This follows mr-manuel's observed per-app Compose/README/icon/screenshot layout.
No standalone `appfile.json` or per-app `store.json` is required by the observed
tree. Add the row from [homeautomation/README-entry.md](homeautomation/README-entry.md)
to the upstream root application's table; do not replace its entire README.
Recheck the row number if more applications have been added.

The category `HomeAutomation` matches that repository's registered category
identifier. Existing older app manifests also contain the spaced spelling
`Home Automation`; this proposal uses the registered identifier and `en_US`
locale keys. Its description explicitly states that Clipboard Bridge does **not**
provide Home Assistant, MQTT, device control or IoT discovery. Ask about scope
before investing in a PR if this companion utility is not a fit.

The icon and screenshots are original project assets with public sample data.
Public upstream project URLs work before this PR is merged; no future fork URL
or private IP is embedded. Only `amd64` and `arm64` are advertised.

PR/scope text: [homeautomation/PR_DESCRIPTION.md](homeautomation/PR_DESCRIPTION.md).

## Shared deployment contract

- One server, TCP `5088`, HTTP `/`, public health check `/health`.
- Persistent `/data`: history, uploads, per-account directories and session key.
- No database, privileged container, host networking, Docker socket or device mapping.
- Optional `CLIPBOARD_TOKEN` protects the general API; optional
  `CLIPBOARD_PASSWORD` protects the general web page. They are separate protections.
- `CLIPBOARD_ACCOUNTS` adds isolated `user:password` pairs while the general
  clipboard remains available. `CLIPBOARD_ACCOUNTS_FILE=/data/accounts.txt` can
  load a private file stored inside the already mounted data directory.
- Empty auth settings leave the shared clipboard open. Use a trusted LAN/private
  VPN; do not forward the service to the internet. URL credentials are readable;
  HTTP is not encrypted. Never submit real credentials or private paths.
- If host port `5088` is occupied, edit the published port and `x-casaos.port_map`
  together; leave internal `CLIPBOARD_PORT`, target port and healthcheck at `5088`.
- These are **new-install proposals**, not migration instructions. Preserve and
  back up existing data; do not install several variants against the same folder.

The image defaults to its existing root user for the Big Bear/HomeAutomation
variants; this package does not silently claim they are rootless. The UID reference
is explicit about permissions and does not change the published image.

## Validate this package

Docker with Compose is needed to validate the resolved Compose models. For the
Python checks use an isolated environment:

```bash
python -m venv .venv-validation
# Activate it in your shell, then:
python -m pip install -r validation/requirements.txt
python validation/validate.py --check-links
```

The validator checks all four Compose files, duplicate YAML keys, actual Big Bear
JSON Schema, main service/port/data/auth contracts, and optional public asset links.
It **does not start containers, change production data, install CasaOS or submit PRs**.
The `validation/.env.compose-check` file supplies only public sample interpolation
values, including Big Bear's `$AppID`, so no private `.env` is needed.

[VALIDATION.md](VALIDATION.md) records checks actually performed and manual checks
still required. Leave CasaOS physical-install checkboxes unticked until tested.

## About store.json and version numbers

Do not confuse Docker Compose file versions, Big Bear's universal schema `1.0`,
and ZimaOS's catalog protocol v2. They are different things. No unsupported
`version: "3"` or invented app-level `store.json` has been added here.
LinuxServer's current publication workflow generates its v2 catalog from `Apps/`;
Big Bear generates downstream definitions from its universal app; mr-manuel's
observed workflow publishes the existing repository's release archive. Store
owners control their own catalog generation and release processes.

These are independent community stores, not three guaranteed distribution slots.
No acceptance, endorsement or physical-install testing is implied.
