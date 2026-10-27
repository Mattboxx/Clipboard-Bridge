# Title

Eligibility question: independently maintained Clipboard Bridge image

# Body

Hi! I'm the maintainer of [Clipboard Bridge](https://github.com/Mattboxx/Clipboard-Bridge),
a small self-hosted clipboard/file bridge for Windows, Android and Apple Shortcuts.

I read the contributing note asking users not to submit PRs because this catalog
is generated automatically. **I have not submitted a manifest PR.** Before doing
any integration work, could you confirm whether independently maintained images
are out of scope, or whether there is a supported request/generator route?

Project details:

- Image: `ghcr.io/mattboxx/clipboard-bridge-server:1.0.11` (amd64/arm64).
- Single Python service, TCP 5088, persistent `/data`, `/health`, MIT project license.
- Browser uploads/history, file groups and optional isolated accounts.
- Intended for trusted LAN/private VPN use; URL credentials are readable and HTTP
  is unencrypted. No mandatory online account is needed.

The image is **not built or maintained by LinuxServer.io**, is not s6-based and
does not implement LinuxServer `PUID`/`PGID` ownership initialization. I will not
add those environment variables and pretend they make it compatible. A local
reference `custom-import/docker-compose.yml` uses Docker's numeric `user` field
instead, with an explicitly prepared data directory and `TZ=Etc/UTC`; it is not
being proposed as an official LinuxServer container or catalog entry.

If the store is exclusively for LinuxServer.io images, that's completely fine;
no exception is requested. I'll continue distributing the independent Compose
and catalog rather than modifying generated files.

[Source](https://github.com/Mattboxx/Clipboard-Bridge) |
[Docker guide](https://github.com/Mattboxx/Clipboard-Bridge/blob/main/DOCKER.md)

Thank you for clarifying the intended contribution route.
