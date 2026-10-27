# Server 1.0.11

## Changes

- Put optional Ko-fi support at the top of the web page beside a direct GitHub link.
  The existing seven-language support labels and friendly explanation are retained.
- Fixed public destinations, `noopener noreferrer`, and no-referrer policy remain;
  external links do not include account URLs or credentials.
- API routes, accounts, session lifetime, port 5088 and persistent `/data` are unchanged.
  No new runtime dependency. Windows 2.0.20, Android beta.12 and Apple exports unchanged.
- Prepare separately documented third-party CasaOS proposals; this is not store acceptance.

## Delivery

Local validation: 585 Python tests passed (16 environment-dependent skips),
14 disposable Docker tests passed, and browser layout checked at 1280, 390 and
320 pixels in all seven languages. Big Bear's strict checker and CasaOS converter,
all four Compose definitions and public asset links passed. No physical device
or store-UI test is claimed.

Publish `ghcr.io/mattboxx/clipboard-bridge-server:1.0.11` for Linux amd64/arm64
before publishing catalog changes. Retain the stable Windows release as GitHub's
latest desktop download. Never change an already published 1.0.10 tag.

Keep existing data mounts, environment settings and client/Shortcut URLs when
updating. `docker compose pull` with a pinned 1.0.10 tag does not select 1.0.11:
change the image tag explicitly, pull, and recreate without deleting volumes.

Tests and publication evidence are recorded in the delivery PR and CasaOS package
validation report. Physical CasaOS/NAS and ARM64-device checks remain manual.
