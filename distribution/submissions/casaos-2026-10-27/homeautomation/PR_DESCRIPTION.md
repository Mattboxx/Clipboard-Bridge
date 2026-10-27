# Title

Add Clipboard Bridge 1.0.11 as a companion home-server utility

# Body

Hi! I'm the maintainer of [Clipboard Bridge](https://github.com/Mattboxx/Clipboard-Bridge).
Would a companion home-server utility fit this store's scope? It shares text,
photos and files between Windows, Android and Apple Shortcuts, with a browser
interface, persistent history and optional isolated accounts.

**It does not provide home-device control, MQTT or a Home Assistant integration.**
I understand if that makes it out of scope; in that case I'll keep it in the
independent catalog. The following candidate is prepared if you welcome it.

## Proposed files

- `Apps/ClipboardBridge/docker-compose.yml`
- `Apps/ClipboardBridge/README.md`
- `Apps/ClipboardBridge/icon.png`
- `Apps/ClipboardBridge/screenshot-1.png`
- `Apps/ClipboardBridge/screenshot-2.png`
- One new row in the root README's application table.

## Deployment

Public image `ghcr.io/mattboxx/clipboard-bridge-server:1.0.11`, Linux amd64/arm64,
web/API port 5088, health check `/health`, bind-mounted persistent `/data`.
No privileged mode, host networking, devices, Docker socket or database.
The metadata uses the registered `HomeAutomation` category identifier without
claiming that the application itself performs device automation.

Authentication is optional: empty settings leave the shared clipboard open.
Web password and API token are separate protections. URL credentials remain
readable; HTTP is unencrypted. The service is for trusted LAN/private VPN use,
not direct public internet exposure. Screenshots contain public sample data only.

## Checks

- [x] YAML and Docker Compose parsing/resolution checked.
- [x] Main service, ports, persistent path and supported image platforms checked.
- [x] Public project/media links checked.
- [ ] Installation/update/removal tested through this store's CasaOS interface.
- [ ] Physical ARM64 test completed.

I have left the unperformed device/UI checks unticked rather than implying store
installation was tested. Please advise on scope/category before I submit a PR
if you would prefer this as an issue first.

[Setup](https://github.com/Mattboxx/Clipboard-Bridge/blob/main/DOCKER.md) |
[Website](https://mattboxx.github.io/Clipboard-Bridge/)
