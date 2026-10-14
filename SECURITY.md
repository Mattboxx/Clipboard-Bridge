# Security policy

## Supported versions

Security fixes are applied to the latest Windows release and the latest server
container image. Older releases should be upgraded before reporting a problem.

## Report a vulnerability privately

Do not open a public issue for a vulnerability or include credentials,
clipboard contents, private addresses or logs containing sensitive data.

Use the repository's
[private vulnerability reporting form](https://github.com/Mattboxx/Clipboard-Bridge/security/advisories/new).
Include the affected version, operating system, deployment method, reproduction
steps and expected impact. Remove real tokens and passwords from screenshots and
logs.

## Network model

Clipboard Bridge is designed for trusted local networks and private VPNs. The
default HTTP transport is intentionally compatible with iOS Shortcuts and does
not encrypt traffic by itself. Do not expose port `5088` directly to the public
Internet. For remote access, use a private VPN or an HTTPS reverse proxy and
enable the available token, web password or isolated accounts.

Tokens, the web password and isolated accounts are optional. Without them, the
general clipboard is open to the local network. Shortcut and account URLs can
contain `token`, `user` and `password` in plain text; these values can appear in
browser history, logs and screenshots. Treat every such URL as a credential.

The project does not collect telemetry or receive users' clipboard contents.

Native clients and Apple Shortcuts retain compatible account URLs. Optional HTTP
headers are also supported by the standalone API, but neither form encrypts
credentials over HTTP. No interactive login, pairing or token renewal is required.
Windows currently uses HTTP; Android and Apple can use an optional HTTPS endpoint.
Keep Windows connections on a trusted LAN/VPN rather than promising universal TLS.

The Windows embedded server exposes one shared clipboard and does not implement
the standalone server's account/token login. Use it only on a trusted LAN or a
private VPN whose access rules admit trusted devices. Do not forward its port.

Windows configuration and Android app-private preferences currently store
credentials without application-level encryption. Local clipboard histories are
also sensitive. Protect your OS account and backups. DPAPI would protect against
some offline reads, not malware running as the same signed-in user; an encrypted
configuration migration is deferred until downgrade/recovery behavior is tested.

Remembered web sessions default to 3650 days for compatibility. Administrators
can set `CLIPBOARD_SESSION_DAYS` (1..3650); 90 or 365 is a less persistent choice.
Changing a password does not currently revoke all existing browser sessions.
For immediate revocation, stop the service, replace `/data/secret.key`, then
restart it: all devices must log in again, but clipboard files are untouched.
Back up securely first. Keep this disruptive action separate from routine upgrades.
