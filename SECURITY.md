# Security policy

## Supported versions

Security fixes are applied to the latest Windows release and the latest server
container image. Older releases should be upgraded before reporting a problem.

## Dependency Maintenance

For source installations, use a clean virtual environment and install the current
requirements. Candidate minimum versions are Flask 3.1.3, Requests 2.33.0 and
Pillow 12.3.0. The previous ranges permitted older releases with known advisories,
even when a fresh installation normally selected a newer version. Updating these
files does not upgrade an existing virtual environment, container or frozen EXE.

These floors address the reviewed upstream advisories, not every hypothetical
application exploit. For example, the Requests temporary-file advisory applies to
direct callers of `extract_zipped_paths()`, which Clipboard Bridge does not call;
the Flask cache advisory also has deployment-specific preconditions. Pillow handles
untrusted image data, so its image-parser fixes remain important on a trusted LAN.

When reviewing updates, audit both the freshly resolved dependency set (including
transitive dependencies) and the declared direct minimum versions. Deduplicate
advisory IDs before counting findings. Recheck at release time; a clean audit is
time-specific and is not a security certification of already-published binaries.
Major upgrades such as Gunicorn's pending update require their own compatibility
review and running-container tests, not just a manifest change.

Upstream references:
[Flask session/cache advisory](https://github.com/pallets/flask/security/advisories/GHSA-68rp-wp8r-4726),
[Requests temporary-file advisory](https://github.com/psf/requests/security/advisories/GHSA-gc5v-m9x4-r6x2),
[Pillow 12.3.0 security release notes](https://pillow.readthedocs.io/en/stable/releasenotes/12.3.0.html).

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

On case-insensitive or filename-normalizing storage, different account names can
refer to the same directory. The candidate account-storage guard refuses access to
such ambiguous accounts rather than exposing shared history. Prefer names that do
not differ only by case or trailing dots. Back up and review any existing mixed
history before changing account names; the application does not automatically move
or reassign that data. See [account storage recovery](DOCKER.md#security-and-accounts).
