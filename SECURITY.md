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
