# Clipboard Bridge Server 1.0.9

Maintenance release for the standalone Docker/Python host. Windows remains 2.0.17;
Android receives its separate 1.0.0-beta.12 update. Existing signed Apple exports
and optional `user`/`password`/`token` URLs remain compatible.

## Changes

- Preserve existing history and files when an index is malformed or unreadable.
  Return `503 history_unavailable` instead of replacing damaged history with empty data.
- Flush the complete temporary index before atomic replacement. Clean temporary files
  after failed commits and preserve previously indexed files after failed uploads.
- Reject ambiguous account directories on case-insensitive/normalizing filesystems.
  Shared clipboard and unrelated accounts remain available; do not relocate mixed data.
- Use the reviewed Flask 3.1.3 minimum. Keep the existing single threaded-worker
  Gunicorn model, persistent `/data`, port 5088 and API/Apple authentication contract.

## Update

Back up `/data` and retain the same bind mount or Docker volume, ports, accounts and
environment settings. Change only the image to:

```text
ghcr.io/mattboxx/clipboard-bridge-server:1.0.9
```

The stable image supports `linux/amd64` and `linux/arm64`. Catalogs are published
only after the versioned image is available. Custom sources are not official store
inclusion. Refresh the store after its catalog deployment completes.

Use a trusted LAN/private VPN. Credentials in URLs remain readable and HTTP is not
encrypted. These automated storage/API checks are not physical NAS/VPN/device tests.
