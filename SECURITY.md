# Security policy

## Supported versions

Security fixes are applied to the latest Windows release and the latest server
container image. Older releases should be upgraded before reporting a problem.

## Report a vulnerability privately

Do not open a public issue for a vulnerability or include credentials,
clipboard contents, private addresses or logs containing sensitive data.

Use the repository's
[private vulnerability reporting form](https://github.com/mattbox03/Clipboard-Bridge/security/advisories/new).
Include the affected version, operating system, deployment method, reproduction
steps and expected impact. Remove real tokens and passwords from screenshots and
logs.

## Network model

Clipboard Bridge is designed for trusted local networks and private VPNs. The
default HTTP transport is intentionally compatible with iOS Shortcuts and does
not encrypt traffic by itself. Do not expose port `5088` directly to the public
Internet. For remote access, use a private VPN or an HTTPS reverse proxy and
enable the available token, web password or isolated accounts.

The project does not collect telemetry or receive users' clipboard contents.
