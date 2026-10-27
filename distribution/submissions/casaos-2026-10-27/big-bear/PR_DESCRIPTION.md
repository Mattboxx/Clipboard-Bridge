# Title

feat: add Clipboard Bridge 1.0.11 (CasaOS universal definition)

# Body

## Summary

I'm the maintainer of [Clipboard Bridge](https://github.com/Mattboxx/Clipboard-Bridge),
a self-hosted clipboard/file bridge for Windows, Android and Apple Shortcuts.
This proposal adds a universal source definition rather than hand-editing the
generated CasaOS store. It enables the CasaOS conversion only.

## Files

- `apps/clipboard-bridge/app.json`
- `apps/clipboard-bridge/docker-compose.yml`
- `apps/clipboard-bridge/README.md`

The Compose file is platform-neutral, with no `x-casaos` extension. The converter
produces the CasaOS metadata, app ID and `/DATA/AppData/$AppID/data` mapping.
No root store catalog or generated application list is manually replaced.

## Runtime and security

- Public image: `ghcr.io/mattboxx/clipboard-bridge-server:1.0.11`, Linux amd64/arm64.
- Single service; TCP 5088, `/health`, persistent `/data`; no database or host privileges.
- Browser uploads/history, grouped files and optional isolated accounts.
- Shared authentication is optional and empty initially. Web password and API
  token protect different entry points; URL credentials are readable and HTTP
  is unencrypted. Intended for trusted LAN/private VPN access, not public exposure.
- Image is independently maintained by this project, not LinuxServer.io.

## Validation

- [x] Docker Compose parsing and resolved deployment contracts checked.
- [x] `app.json` validated against the inspected upstream JSON Schema.
- [x] Upstream `validate-apps.sh --strict` and CasaOS conversion completed.
- [x] Public icon/screenshot links checked.
- [ ] Manual installation and update tested through the CasaOS App Store UI.
- [ ] Physical ARM64/CasaOS device test completed.

The unchecked items are not claimed as completed. I can provide the local
validation report; please let me know if you prefer different categorization or
additional checks before review.

[Docker guide](https://github.com/Mattboxx/Clipboard-Bridge/blob/main/DOCKER.md) |
[Demo and tutorial](https://mattboxx.github.io/Clipboard-Bridge/tutorial.html)
